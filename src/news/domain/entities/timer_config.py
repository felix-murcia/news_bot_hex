"""Timer configuration domain entity.

Represents the scheduling configuration for the news pipeline.
This is a value object (frozen dataclass) with immutability and validation.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TimerFrequency(str, Enum):
    """Supported frequency options for timer scheduling."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass(frozen=True)
class TimerConfig:
    """Immutable value object for timer configuration.

    Represents the active scheduling configuration for the news pipeline,
    including whether it's enabled and when it should run.

    Attributes:
        enabled: Whether the timer is active
        schedule_time: Time in HH:MM format (24-hour)
        frequency: How often to execute (hourly/daily/weekly/monthly)
        created_at: When this configuration was created
        updated_at: When this configuration was last modified
    """
    enabled: bool
    schedule_time: str  # HH:MM format
    frequency: TimerFrequency
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate configuration on instantiation."""
        # Validate schedule_time format (HH:MM)
        if not re.match(r'^\d{2}:\d{2}$', self.schedule_time):
            raise ValueError(f"Invalid schedule_time format: {self.schedule_time}. Use HH:MM format.")

        # Validate hours and minutes are in range
        try:
            hour, minute = map(int, self.schedule_time.split(':'))
            if not (0 <= hour < 24):
                raise ValueError(f"Hour must be 0-23, got {hour}")
            if not (0 <= minute < 60):
                raise ValueError(f"Minute must be 0-59, got {minute}")
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError(f"Invalid schedule_time: {self.schedule_time}") from e
            raise

    @classmethod
    def from_dict(cls, data: dict) -> 'TimerConfig':
        """Reconstruct domain entity from dictionary (e.g., from MongoDB)."""
        return cls(
            enabled=data['enabled'],
            schedule_time=data['schedule_time'],
            frequency=TimerFrequency(data['frequency']),
            created_at=data.get('created_at', datetime.now()),
            updated_at=data.get('updated_at', datetime.now()),
        )

    def to_dict(self) -> dict:
        """Serialize domain entity to dictionary (e.g., for MongoDB)."""
        return {
            'enabled': self.enabled,
            'schedule_time': self.schedule_time,
            'frequency': self.frequency.value,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
