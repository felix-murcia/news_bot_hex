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
    BUSINESS_HOURS = "business_hours"  # Hourly, Mon-Fri, within [schedule_time, end_time]


@dataclass(frozen=True)
class TimerConfig:
    """Immutable value object for timer configuration.

    Represents the active scheduling configuration for the news pipeline,
    including whether it's enabled and when it should run.

    Attributes:
        enabled: Whether the timer is active
        schedule_time: Time in HH:MM format (24-hour). For business_hours,
            this is the start of the daily window.
        frequency: How often to execute (hourly/daily/weekly/monthly/business_hours)
        end_time: Required only for business_hours; end of the daily window (HH:MM)
        created_at: When this configuration was created
        updated_at: When this configuration was last modified
    """
    enabled: bool
    schedule_time: str  # HH:MM format
    frequency: TimerFrequency
    end_time: Optional[str] = None  # HH:MM format, business_hours only
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate configuration on instantiation."""
        self._validate_time_format(self.schedule_time, "schedule_time")

        if self.frequency == TimerFrequency.BUSINESS_HOURS:
            if not self.end_time:
                raise ValueError("end_time is required when frequency is 'business_hours'")
            self._validate_time_format(self.end_time, "end_time")

            start_hour = int(self.schedule_time.split(':')[0])
            end_hour = int(self.end_time.split(':')[0])
            if end_hour <= start_hour:
                raise ValueError(
                    f"end_time hour ({end_hour}) must be after schedule_time hour ({start_hour})"
                )

    @staticmethod
    def _validate_time_format(value: str, field_name: str) -> None:
        """Validate a HH:MM time string."""
        if not re.match(r'^\d{2}:\d{2}$', value):
            raise ValueError(f"Invalid {field_name} format: {value}. Use HH:MM format.")

        try:
            hour, minute = map(int, value.split(':'))
            if not (0 <= hour < 24):
                raise ValueError(f"Hour must be 0-23, got {hour}")
            if not (0 <= minute < 60):
                raise ValueError(f"Minute must be 0-59, got {minute}")
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError(f"Invalid {field_name}: {value}") from e
            raise

    @classmethod
    def from_dict(cls, data: dict) -> 'TimerConfig':
        """Reconstruct domain entity from dictionary (e.g., from MongoDB)."""
        return cls(
            enabled=data['enabled'],
            schedule_time=data['schedule_time'],
            frequency=TimerFrequency(data['frequency']),
            end_time=data.get('end_time'),
            created_at=data.get('created_at', datetime.now()),
            updated_at=data.get('updated_at', datetime.now()),
        )

    def to_dict(self) -> dict:
        """Serialize domain entity to dictionary (e.g., for MongoDB)."""
        return {
            'enabled': self.enabled,
            'schedule_time': self.schedule_time,
            'frequency': self.frequency.value,
            'end_time': self.end_time,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
