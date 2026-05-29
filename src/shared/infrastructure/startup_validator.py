"""
Startup Validator - Validates critical infrastructure before application starts.

This module ensures that all mandatory infrastructure pre-requisites are met:
- Database is connected and is 'appdb'
- Database contains minimum required data
- Required collections exist and have data

If any validation fails, the application MUST NOT start. This is a hard stop.
"""

import os
import sys
from typing import Tuple

from config.logging_config import get_logger
from src.shared.adapters.mongo_db import get_database

logger = get_logger("news_bot.startup.validator")


class InfrastructureValidationError(Exception):
    """Raised when critical infrastructure validation fails."""
    pass


class StartupValidator:
    """Validates infrastructure is correct before application starts."""

    # Critical thresholds - if these are not met, something is wrong
    MIN_ARTICLES = 1000  # Should have 21K+ but 1K is bare minimum
    MIN_RSS_SOURCES = 10  # Should have 18
    REQUIRED_COLLECTIONS = {
        'sources_rss': 'RSS sources configuration',
        'raw_news': 'Raw news articles',
        'verified_news': 'Verified articles',
    }

    @staticmethod
    def validate_all() -> None:
        """Run all validations. Raises InfrastructureValidationError if any fail."""
        logger.info("=" * 70)
        logger.info("STARTUP INFRASTRUCTURE VALIDATION")
        logger.info("=" * 70)

        try:
            StartupValidator._validate_database_name()
            StartupValidator._validate_database_connection()
            StartupValidator._validate_data_quantities()
            StartupValidator._validate_required_collections()
            StartupValidator._ensure_timer_initialized()

            logger.info("=" * 70)
            logger.info("✅ ALL INFRASTRUCTURE VALIDATIONS PASSED")
            logger.info("=" * 70)

        except InfrastructureValidationError as e:
            logger.error("=" * 70)
            logger.error("❌ INFRASTRUCTURE VALIDATION FAILED")
            logger.error("=" * 70)
            logger.error(f"\n{str(e)}\n")
            logger.error("Application cannot start. Fix infrastructure and retry.")
            logger.error("=" * 70)
            sys.exit(1)

    @staticmethod
    def _validate_database_name() -> None:
        """Verify MONGO_DB_NAME environment variable is 'appdb'."""
        db_name = os.getenv('MONGO_DB_NAME', '').strip()

        logger.info(f"[1/4] Validating database name...")
        logger.info(f"      MONGO_DB_NAME = '{db_name}'")

        if not db_name:
            raise InfrastructureValidationError(
                "MONGO_DB_NAME environment variable not set.\n"
                "       Required: MONGO_DB_NAME=appdb"
            )

        if db_name != 'appdb':
            raise InfrastructureValidationError(
                f"MONGO_DB_NAME is '{db_name}' but MUST be 'appdb'.\n"
                f"       Reason: 'appdb' contains all real data (21K+ articles)\n"
                f"       Fix: Set MONGO_DB_NAME=appdb in .env\n"
                f"       Current value '{db_name}' is likely empty or incorrect."
            )

        logger.info(f"      ✅ Database name is correct: 'appdb'")

    @staticmethod
    def _validate_database_connection() -> None:
        """Verify MongoDB connection works."""
        logger.info(f"[2/4] Validating database connection...")

        try:
            db = get_database()
            # Ping to verify connection
            db.command('ping')
            db_name = db.name
            logger.info(f"      ✅ Connected to MongoDB database: '{db_name}'")

        except Exception as e:
            raise InfrastructureValidationError(
                f"Failed to connect to MongoDB.\n"
                f"       Error: {str(e)}\n"
                f"       Verify MongoDB is running and credentials are correct."
            )

    @staticmethod
    def _validate_data_quantities() -> None:
        """Verify database has minimum required data."""
        logger.info(f"[3/4] Validating data quantities...")

        db = get_database()

        # Check article count
        article_count = db['raw_news'].count_documents({})
        logger.info(f"      Articles in raw_news: {article_count:,}")

        if article_count < StartupValidator.MIN_ARTICLES:
            raise InfrastructureValidationError(
                f"Insufficient articles in database.\n"
                f"       Expected: {StartupValidator.MIN_ARTICLES:,}+ articles\n"
                f"       Found: {article_count:,} articles\n"
                f"       This suggests database is not 'appdb' or appdb is not initialized.\n"
                f"       Verify MONGO_DB_NAME=appdb and MongoDB data exists."
            )

        # Check RSS sources
        try:
            sources_doc = db['sources_rss'].find_one({"_id": "sources"})
            sources_count = len(sources_doc.get('sources', [])) if sources_doc else 0
            logger.info(f"      RSS sources configured: {sources_count}")

            if sources_count < StartupValidator.MIN_RSS_SOURCES:
                raise InfrastructureValidationError(
                    f"Insufficient RSS sources configured.\n"
                    f"       Expected: {StartupValidator.MIN_RSS_SOURCES}+ sources\n"
                    f"       Found: {sources_count} sources\n"
                    f"       This suggests database is not 'appdb' or sources not initialized."
                )
        except Exception as e:
            if isinstance(e, InfrastructureValidationError):
                raise
            raise InfrastructureValidationError(
                f"Failed to read RSS sources from database.\n"
                f"       Error: {str(e)}\n"
                f"       Verify 'sources_rss' collection exists with sources data."
            )

        logger.info(f"      ✅ Data quantities are valid")

    @staticmethod
    def _validate_required_collections() -> None:
        """Verify all required collections exist."""
        logger.info(f"[4/4] Validating required collections...")

        db = get_database()
        existing_collections = set(db.list_collection_names())

        for collection_name, description in StartupValidator.REQUIRED_COLLECTIONS.items():
            if collection_name not in existing_collections:
                raise InfrastructureValidationError(
                    f"Required collection '{collection_name}' does not exist.\n"
                    f"       Purpose: {description}\n"
                    f"       This collection must be present in appdb."
                )

            count = db[collection_name].count_documents({})
            status = "✅" if count > 0 else "⚠️ "
            logger.info(f"      {status} {collection_name}: {count:,} documents")

        logger.info(f"      ✅ All required collections exist")

    @staticmethod
    def _ensure_timer_initialized() -> None:
        """Ensure systemd timer is initialized and regenerated on startup."""
        logger.info(f"[5/5] Initializing systemd timer...")

        try:
            db = get_database()
            timer_config = db['timer_config'].find_one({'_id': 'pipeline_timer'})

            if not timer_config:
                # Create default timer configuration if not present
                from datetime import datetime
                default_config = {
                    '_id': 'pipeline_timer',
                    'enabled': True,
                    'schedule_time': '00:00',
                    'frequency': 'daily',
                    'created_at': datetime.now(),
                    'updated_at': datetime.now(),
                }
                db['timer_config'].insert_one(default_config)
                logger.info("      Created default timer config: daily at 00:00")
                timer_config = default_config

            # Regenerate systemd timer file with current configuration
            try:
                from src.news.infrastructure.adapters.systemd_timer_adapter import SystemdTimerAdapter
                from src.news.domain.entities.timer_config import TimerConfig

                config_obj = TimerConfig.from_dict(timer_config)
                adapter = SystemdTimerAdapter()
                adapter.regenerate_timer_file(config_obj)
                logger.info(f"      ✅ Systemd timer regenerated: {config_obj.frequency.value} at {config_obj.schedule_time}")
            except Exception as e:
                logger.warning(f"      ⚠️  Could not regenerate systemd timer: {str(e)}")
                logger.info(f"      (Timer may be running in Docker without systemd)")

        except Exception as e:
            if isinstance(e, InfrastructureValidationError):
                raise
            # Non-critical failure - timer is not essential for application to work
            logger.warning(f"      ⚠️  Timer initialization failed (non-critical): {str(e)}")


def validate_startup_infrastructure() -> None:
    """
    Public entry point for startup validation.

    Should be called at application startup, before any routers are registered.
    If validation fails, application will exit with status code 1.
    """
    StartupValidator.validate_all()
