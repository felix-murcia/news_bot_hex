"""FastAPI Router for Administrative Endpoints.

Handles infrastructure configuration: timers, providers, and system status.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import subprocess
from datetime import datetime

from config.logging_config import get_logger
from config.settings import Settings
from src.news.domain.entities.timer_config import TimerFrequency
from src.news.domain.ports.timer_config_repository_port import TimerConfigRepositoryPort
from src.news.entrypoints.api.dependencies import get_timer_config_repository

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
async def get_timer_config(timer_repo: TimerConfigRepositoryPort = Depends(get_timer_config_repository)):
    """Get current timer configuration."""
    try:
        config = await timer_repo.get_current()
        if not config:
            raise HTTPException(status_code=404, detail="Timer configuration not found")

        return PipelineResponse(
            status="ok",
            message="Timer configuration retrieved",
            data={
                "enabled": config.enabled,
                "schedule_time": config.schedule_time,
                "frequency": config.frequency.value,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting timer config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timer/config", response_model=PipelineResponse)
async def update_timer_config(
    config: TimerConfig,
    timer_repo: TimerConfigRepositoryPort = Depends(get_timer_config_repository)
):
    """Update timer configuration."""
    try:
        from src.news.infrastructure.adapters.systemd_timer_adapter import SystemdTimerAdapter
        from src.news.domain.entities.timer_config import TimerConfig as DomainTimerConfig

        # Create domain entity from request
        domain_config = DomainTimerConfig(
            enabled=config.enabled,
            schedule_time=config.schedule_time,
            frequency=TimerFrequency(config.frequency),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Save configuration to MongoDB
        updated = await timer_repo.save(domain_config)
        logger.info(f"[TIMER] Config saved: {updated.to_dict()}")

        # Regenerate systemd timer file with new configuration
        systemd_adapter = SystemdTimerAdapter()
        systemd_adapter.regenerate_timer_file(updated)
        logger.info(f"[TIMER] Timer file regenerated")

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

        logger.info(f"[TIMER] Configuration updated: enabled={updated.enabled}, schedule={updated.frequency.value} at {updated.schedule_time}{control_message}")

        return PipelineResponse(
            status="ok",
            message=f"Timer configuration updated{control_message}",
            data={
                "enabled": updated.enabled,
                "schedule_time": updated.schedule_time,
                "frequency": updated.frequency.value,
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
async def get_timer_status(timer_repo: TimerConfigRepositoryPort = Depends(get_timer_config_repository)):
    """Get systemd timer status (or fallback if running in Docker)."""
    try:
        config = await timer_repo.get_current()
        if not config:
            return PipelineResponse(
                status="ok",
                message="Timer status (no configuration)",
                data={
                    "active": False,
                    "status_output": "No timer configuration found",
                }
            )

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
            timers_output = f"Schedule: {config.schedule_time} ({config.frequency.value})"
        except Exception as e:
            logger.warning(f"[TIMER] Could not get systemd status: {e}")
            is_active = config.enabled
            status_output = f"Timer is {'enabled' if config.enabled else 'disabled'} (status unavailable)"
            timers_output = f"Schedule: {config.schedule_time} ({config.frequency.value})"

        return PipelineResponse(
            status="ok",
            message="Timer status retrieved",
            data={
                "active": is_active,
                "enabled": config.enabled,
                "schedule_time": config.schedule_time,
                "frequency": config.frequency.value,
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
