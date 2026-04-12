"""
MongoDB Repository for News Validation Rules.

Stores and retrieves validation configuration (stopwords, sensationalist words,
scoring rules, thresholds) from MongoDB instead of hardcoded values.
"""

from typing import Dict, Any, Optional, List
from config.logging_config import get_logger

logger = get_logger("news_bot.infra.validation_rules")


class MongoValidationRulesRepository:
    """Repository for news validation rules stored in MongoDB."""

    COLLECTION_NAME = "validation_rules"

    def __init__(self):
        from src.shared.adapters.mongo_db import get_database

        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    def get_rules(self, rule_type: str = "default") -> Optional[Dict[str, Any]]:
        """
        Get validation rules from MongoDB.
        
        Args:
            rule_type: Type of rules to retrieve (e.g., "default", "english", "spanish")
            
        Returns:
            Dictionary with validation rules or None if not found
        """
        try:
            rules = self._collection.find_one({"_id": rule_type})
            if rules:
                # Remove MongoDB _id field
                rules.pop("_id", None)
                return rules
            logger.warning(f"Validation rules '{rule_type}' not found in MongoDB")
            return None
        except Exception as e:
            logger.error(f"Error retrieving validation rules: {e}")
            return None

    def get_stopwords(self, language: str = "english") -> List[str]:
        """Get stopwords for the specified language."""
        rules = self.get_rules(f"stopwords_{language}")
        if rules and "words" in rules:
            return rules["words"]
        return []

    def get_sensationalist_words(self, rule_type: str = "default") -> List[str]:
        """Get sensationalist word patterns."""
        rules = self.get_rules(f"sensationalist_{rule_type}")
        if rules and "words" in rules:
            return rules["words"]
        return []

    def get_source_indicators(self, rule_type: str = "default") -> List[str]:
        """Get source indicator phrases that increase credibility."""
        rules = self.get_rules(f"source_indicators_{rule_type}")
        if rules and "phrases" in rules:
            return rules["phrases"]
        return []

    def get_scoring_config(self, rule_type: str = "default") -> Dict[str, Any]:
        """Get scoring configuration."""
        rules = self.get_rules(f"scoring_{rule_type}")
        if rules:
            return rules
        return {}

    def get_date_patterns(self, rule_type: str = "default") -> List[str]:
        """Get date patterns that increase credibility."""
        rules = self.get_rules(f"date_patterns_{rule_type}")
        if rules and "patterns" in rules:
            return rules["patterns"]
        return []

    def save_rules(self, rule_id: str, rules: Dict[str, Any]) -> bool:
        """
        Save validation rules to MongoDB.
        
        Args:
            rule_id: Unique identifier for the rules
            rules: Dictionary with validation rules
            
        Returns:
            True if successful, False otherwise
        """
        try:
            rules["_id"] = rule_id
            self._collection.replace_one(
                {"_id": rule_id}, rules, upsert=True
            )
            logger.info(f"Validation rules '{rule_id}' saved to MongoDB")
            return True
        except Exception as e:
            logger.error(f"Error saving validation rules: {e}")
            return False

    def get_all_rules(self) -> List[Dict[str, Any]]:
        """Get all validation rules."""
        try:
            return list(self._collection.find({}))
        except Exception as e:
            logger.error(f"Error retrieving all validation rules: {e}")
            return []

    def delete_rules(self, rule_id: str) -> bool:
        """Delete validation rules."""
        try:
            result = self._collection.delete_one({"_id": rule_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting validation rules: {e}")
            return False
