"""Port (outbound interface) for timer configuration persistence.

Defines the contract for storing and retrieving timer configuration.
Any adapter (MongoDB, PostgreSQL, etc.) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from src.news.domain.entities.timer_config import TimerConfig


class TimerConfigRepositoryPort(ABC):
    """Outbound port for timer configuration persistence.

    Defines the contract for storing and retrieving timer configuration.
    Implementations may use different backends (MongoDB, files, databases, etc.).

    No infrastructure dependencies leak into this interface - it only works
    with domain entities (TimerConfig).
    """

    @abstractmethod
    async def get_current(self) -> Optional[TimerConfig]:
        """Retrieve the currently active timer configuration.

        Returns:
            The active TimerConfig, or None if no configuration exists yet.
        """
        pass

    @abstractmethod
    async def save(self, config: TimerConfig) -> TimerConfig:
        """Persist timer configuration as the new active configuration.

        Previous active configurations are archived (marked as inactive).
        This creates an audit trail for configuration changes.

        Args:
            config: The TimerConfig to save

        Returns:
            The saved TimerConfig (with timestamps set by persistence layer)

        Raises:
            Exception: If persistence fails
        """
        pass

    @abstractmethod
    async def get_history(self, limit: int = 10) -> List[TimerConfig]:
        """Retrieve configuration history for audit trail.

        Returns previous (inactive) configurations in reverse chronological order,
        allowing visibility into configuration change history.

        Args:
            limit: Maximum number of historical configurations to return

        Returns:
            List of previous TimerConfig objects, newest first. Empty list if no history.
        """
        pass
