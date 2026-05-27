"""Timer configuration management for scheduled pipeline execution."""

import json
import os
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass, asdict

@dataclass
class TimerConfig:
    """Configuration for the news pipeline timer."""
    enabled: bool = True
    schedule_time: str = "08:00"  # HH:MM format
    frequency: str = "daily"  # daily, weekly, etc.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimerConfig":
        return cls(**data)


class TimerConfigManager:
    """Manages persistent timer configuration."""

    def __init__(self):
        config_dir = Path(os.getenv("CONFIG_DIR", Path(__file__).parent))
        self.config_file = config_dir / "timer_config.json"
        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        """Create default config if it doesn't exist."""
        if not self.config_file.exists():
            default_config = TimerConfig()
            self.save_config(default_config)

    def load_config(self) -> TimerConfig:
        """Load timer configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                return TimerConfig.from_dict(data)
        except Exception as e:
            print(f"Error loading timer config: {e}")
        return TimerConfig()

    def save_config(self, config: TimerConfig) -> bool:
        """Save timer configuration to file."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving timer config: {e}")
            return False

    def update_config(self, **kwargs) -> TimerConfig:
        """Update specific config fields."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        self.save_config(config)
        return config


# Global instance
_timer_manager = TimerConfigManager()


def get_timer_config() -> TimerConfig:
    """Get current timer configuration."""
    return _timer_manager.load_config()


def update_timer_config(**kwargs) -> TimerConfig:
    """Update timer configuration."""
    return _timer_manager.update_config(**kwargs)
