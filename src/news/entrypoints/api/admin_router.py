"""FastAPI Router for Administrative Endpoints.

Handles infrastructure configuration: timers, providers, and system status.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import subprocess

from config.logging_config import get_logger
from config.settings import Settings

logger = get_logger("news_bot.api.admin")

router = APIRouter(tags=["admin"])


class PipelineResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


class TimerConfig(BaseModel):
    enabled: bool
    schedule_time: str
    frequency: str = "daily"


@router.get("/timer/config", response_model=PipelineResponse)
def get_timer_config():
    """Get current timer configuration."""
    try:
        from config.timer_config import get_timer_config

        config = get_timer_config()
        return PipelineResponse(
            status="ok",
            message="Timer configuration retrieved",
            data={
                "enabled": config.enabled,
                "schedule_time": config.schedule_time,
                "frequency": config.frequency,
            }
        )
    except Exception as e:
        logger.error(f"Error getting timer config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timer/config", response_model=PipelineResponse)
def update_timer_config(config: TimerConfig):
    """Update timer configuration."""
    try:
        from config.timer_config import update_timer_config, regenerate_systemd_timer

        # Save configuration to file
        updated = update_timer_config(
            enabled=config.enabled,
            schedule_time=config.schedule_time,
            frequency=config.frequency
        )

        # Regenerate systemd timer file with new configuration
        regenerate_systemd_timer(updated)

        control_message = ""
        try:
            # Reload systemd daemon to pick up timer file changes
            result = subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                logger.warning(f"[TIMER] daemon-reload failed: {result.stderr}")

            if config.enabled:
                # Stop and start to apply new schedule
                subprocess.run(
                    ["systemctl", "--user", "stop", "news-bot-pipeline.timer"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                result = subprocess.run(
                    ["systemctl", "--user", "start", "news-bot-pipeline.timer"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    control_message = " (Timer reloaded and started)"
                else:
                    control_message = f" (Timer reload failed: {result.stderr})"
            else:
                result = subprocess.run(
                    ["systemctl", "--user", "stop", "news-bot-pipeline.timer"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    control_message = " (Timer stopped)"
        except Exception as e:
            logger.warning(f"[TIMER] Could not control systemctl: {e}")
            if not config.enabled:
                control_message = " (Manual control via: systemctl --user stop news-bot-pipeline.timer)"
            else:
                control_message = " (Manual control via: systemctl --user start news-bot-pipeline.timer)"

        logger.info(f"[TIMER] Configuration updated: enabled={updated.enabled}, schedule={updated.frequency} at {updated.schedule_time}{control_message}")

        return PipelineResponse(
            status="ok",
            message=f"Timer configuration updated{control_message}",
            data={
                "enabled": updated.enabled,
                "schedule_time": updated.schedule_time,
                "frequency": updated.frequency,
            }
        )
    except Exception as e:
        logger.error(f"Error updating timer config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers", response_model=PipelineResponse)
def get_supported_providers():
    """Get list of supported AI providers."""
    try:
        providers = list(Settings.AI_ADAPTER_MAP.keys())
        return PipelineResponse(
            status="ok",
            message="Supported providers retrieved",
            data={"providers": providers}
        )
    except Exception as e:
        logger.error(f"Error getting supported providers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timer/status", response_model=PipelineResponse)
def get_timer_status():
    """Get systemd timer status (or fallback if running in Docker)."""
    try:
        from config.timer_config import get_timer_config

        config = get_timer_config()

        is_active = None
        status_output = ""
        timers_output = ""

        try:
            result = subprocess.run(
                ["systemctl", "--user", "status", "news-bot-pipeline.timer"],
                capture_output=True,
                text=True,
                timeout=10
            )
            is_active = result.returncode == 0
            status_output = result.stdout

            next_exec = subprocess.run(
                ["systemctl", "--user", "list-timers", "news-bot-pipeline.timer", "--no-pager"],
                capture_output=True,
                text=True,
                timeout=10
            )
            timers_output = next_exec.stdout
        except FileNotFoundError:
            logger.info("[TIMER] systemctl not available (running in Docker?), using config status")
            is_active = config.enabled
            status_output = f"Timer is {'enabled' if config.enabled else 'disabled'} (systemctl unavailable)"
            timers_output = f"Schedule: {config.schedule_time} ({config.frequency})"
        except Exception as e:
            logger.warning(f"[TIMER] Could not get systemd status: {e}")
            is_active = config.enabled
            status_output = f"Timer is {'enabled' if config.enabled else 'disabled'} (status unavailable)"
            timers_output = f"Schedule: {config.schedule_time} ({config.frequency})"

        return PipelineResponse(
            status="ok",
            message="Timer status retrieved",
            data={
                "active": is_active,
                "enabled": config.enabled,
                "schedule_time": config.schedule_time,
                "frequency": config.frequency,
                "status_output": status_output,
                "timers_output": timers_output,
            }
        )
    except Exception as e:
        logger.error(f"Error getting timer status: {e}", exc_info=True)
        return PipelineResponse(
            status="ok",
            message="Timer status (fallback)",
            data={
                "active": False,
                "status_output": "Status unavailable",
                "error": str(e)
            }
        )
