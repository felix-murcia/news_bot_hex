"""Adapter for systemd timer management.

Handles generation and persistence of systemd timer files based on
domain TimerConfig entities. This adapter encapsulates infrastructure
concerns (systemd file I/O) away from business logic.
"""

from pathlib import Path
from src.news.domain.entities.timer_config import TimerConfig
from config.logging_config import get_logger

logger = get_logger("news_bot.adapters.systemd_timer")


class SystemdTimerAdapter:
    """Manages systemd timer file generation and persistence."""

    TIMER_NAME = "news-bot-pipeline.timer"
    SERVICE_NAME = "news-bot-pipeline.service"

    def regenerate_timer_file(self, config: TimerConfig) -> bool:
        """Generate systemd timer file from domain configuration.

        Args:
            config: TimerConfig domain entity

        Returns:
            True if successful, False otherwise
        """
        try:
            systemd_user_dir = Path.home() / ".config/systemd/user"
            timer_file = systemd_user_dir / self.TIMER_NAME

            # Generate OnCalendar directive based on frequency and schedule_time
            hour, minute = config.schedule_time.split(":")

            on_calendar = self._generate_oncalendar(
                config.frequency.value, hour, minute
            )

            # Generate timer file content
            timer_content = self._generate_timer_content(
                config.frequency.value, config.schedule_time, on_calendar
            )

            # Ensure directory exists
            systemd_user_dir.mkdir(parents=True, exist_ok=True)

            # Write timer file
            with open(timer_file, 'w') as f:
                f.write(timer_content)

            logger.info(
                f"[SYSTEMD] Timer file regenerated: {timer_file} "
                f"({config.frequency.value} at {config.schedule_time})"
            )
            return True
        except Exception as e:
            logger.error(f"[SYSTEMD] Error regenerating timer file: {e}")
            return False

    def _generate_oncalendar(self, frequency: str, hour: str, minute: str) -> str:
        """Generate OnCalendar directive based on frequency and time.

        Args:
            frequency: Frequency string (hourly, daily, weekly, monthly)
            hour: Hour in HH format (00-23)
            minute: Minute in MM format (00-59)

        Returns:
            OnCalendar directive for systemd
        """
        if frequency == "daily":
            return f"*-*-* {hour}:{minute}:00"
        elif frequency == "weekly":
            return f"Mon *-*-* {hour}:{minute}:00"
        elif frequency == "monthly":
            return f"*-*-01 {hour}:{minute}:00"
        elif frequency == "hourly":
            # Every hour starting from the specified hour
            return f"*-*-* {hour}/1:{minute}:00"
        else:
            # Default to daily
            return f"*-*-* {hour}:{minute}:00"

    def _generate_timer_content(
        self, frequency: str, schedule_time: str, on_calendar: str
    ) -> str:
        """Generate systemd timer file content.

        Args:
            frequency: Frequency string for documentation
            schedule_time: Human-readable schedule time
            on_calendar: OnCalendar directive

        Returns:
            Complete systemd timer file content
        """
        return f"""[Unit]
Description=News Bot Pipeline Timer
Requires={self.SERVICE_NAME}

[Timer]
# Schedule: {frequency} at {schedule_time}
OnCalendar={on_calendar}
Persistent=true
AccuracySec=1m

[Install]
WantedBy=timers.target
"""
