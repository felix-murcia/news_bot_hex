"""MongoDB adapter for timer configuration persistence.

Implements TimerConfigRepositoryPort using MongoDB as the backend.
Maintains audit trail by marking previous configurations as inactive.
"""

from datetime import datetime
from typing import Optional, List

from src.news.domain.ports.timer_config_repository_port import TimerConfigRepositoryPort
from src.news.domain.entities.timer_config import TimerConfig
from config.logging_config import get_logger

logger = get_logger("news_bot.adapters.timer_config")


class MongoTimerConfigRepository(TimerConfigRepositoryPort):
    """MongoDB adapter for timer configuration persistence.

    Uses a single collection with active/inactive flags to maintain both
    the current configuration and audit trail of historical changes.

    Document structure:
        {
            "enabled": bool,
            "schedule_time": "HH:MM",
            "frequency": "daily|hourly|weekly|monthly",
            "created_at": datetime,
            "updated_at": datetime,
            "is_active": bool,
        }
    """

    COLLECTION_NAME = "timer_config"

    def __init__(self, db=None):
        """Initialize repository with MongoDB database.

        Args:
            db: pymongo Database instance. If None, uses default from get_database()
        """
        if db is None:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()

        self._db = db
        self._collection = self._db[self.COLLECTION_NAME]
        self._ensure_indices()

    def _ensure_indices(self) -> None:
        """Create indices for efficient queries."""
        try:
            # Index for finding active configuration
            self._collection.create_index("is_active")
            # Index for sorting history by creation time
            self._collection.create_index([("created_at", -1)])
        except Exception as e:
            logger.warning(f"[TIMER] Index creation failed: {e}")

    async def get_current(self) -> Optional[TimerConfig]:
        """Retrieve the active timer configuration.

        Returns:
            TimerConfig if an active configuration exists, None otherwise
        """
        try:
            doc = self._collection.find_one({"is_active": True})
            if doc:
                return self._doc_to_entity(doc)
            return None
        except Exception as e:
            logger.error(f"[TIMER] Failed to get current config: {e}")
            return None

    async def save(self, config: TimerConfig) -> TimerConfig:
        """Save configuration as active, archive any previous active configuration.

        Args:
            config: TimerConfig to save

        Returns:
            The saved TimerConfig

        Raises:
            Exception: If database operation fails
        """
        try:
            # Deactivate any previous active configuration
            self._collection.update_many(
                {"is_active": True},
                {"$set": {"is_active": False}}
            )

            # Insert new active configuration
            doc = self._entity_to_doc(config, is_active=True)
            self._collection.insert_one(doc)

            logger.info(
                f"[TIMER] Config saved: {config.schedule_time} {config.frequency.value}, "
                f"enabled={config.enabled}"
            )
            return config
        except Exception as e:
            logger.error(f"[TIMER] Failed to save config: {e}")
            raise

    async def get_history(self, limit: int = 10) -> List[TimerConfig]:
        """Retrieve configuration history (previous inactive configs).

        Args:
            limit: Maximum number of historical entries to return

        Returns:
            List of previous TimerConfig objects in reverse chronological order
        """
        try:
            docs = self._collection.find(
                {"is_active": False}
            ).sort("created_at", -1).limit(limit)

            return [self._doc_to_entity(doc) for doc in docs]
        except Exception as e:
            logger.error(f"[TIMER] Failed to get history: {e}")
            return []

    def _entity_to_doc(self, config: TimerConfig, is_active: bool = True) -> dict:
        """Convert domain entity to MongoDB document.

        Args:
            config: TimerConfig domain entity
            is_active: Whether this is the active configuration

        Returns:
            MongoDB document dictionary
        """
        return {
            "enabled": config.enabled,
            "schedule_time": config.schedule_time,
            "frequency": config.frequency.value,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
            "is_active": is_active,
        }

    def _doc_to_entity(self, doc: dict) -> TimerConfig:
        """Convert MongoDB document to domain entity.

        Args:
            doc: MongoDB document

        Returns:
            TimerConfig domain entity
        """
        return TimerConfig.from_dict({
            "enabled": doc["enabled"],
            "schedule_time": doc["schedule_time"],
            "frequency": doc["frequency"],
            "created_at": doc.get("created_at", datetime.now()),
            "updated_at": doc.get("updated_at", datetime.now()),
        })
