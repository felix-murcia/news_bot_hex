"""
Classic Fake News Validator — domain logic only.

Heuristic rules for news validation with configuration loaded from MongoDB.
Falls back to hardcoded defaults if MongoDB is unavailable.
"""

import re
import string
from typing import Tuple, Optional, List
from config.settings import Settings
from src.logging_config import get_logger

logger = get_logger("news_bot.validator")


class ValidationRulesCache:
    """Cache for validation rules loaded from MongoDB."""
    
    _instance = None
    _stopwords: Optional[frozenset] = None
    _sensationalist_words: Optional[frozenset] = None
    _source_indicators: Optional[List[str]] = None
    _scoring_config: Optional[dict] = None
    _date_patterns: Optional[List[str]] = None
    _loaded: bool = False
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def load_from_mongodb(self) -> bool:
        """
        Load validation rules from MongoDB.
        Returns True if successful, False if fallback to defaults is needed.
        """
        if self._loaded:
            return True
            
        try:
            from src.news.infrastructure.adapters.mongo_validation_rules import (
                MongoValidationRulesRepository,
            )
            
            repo = MongoValidationRulesRepository()
            loaded_any = False
            
            # Load stopwords
            stopwords = repo.get_stopwords("english")
            if stopwords:
                self._stopwords = frozenset(stopwords)
                loaded_any = True
            
            # Load sensationalist words
            sensationalist = repo.get_sensationalist_words()
            if sensationalist:
                self._sensationalist_words = frozenset(sensationalist)
                loaded_any = True
            
            # Load source indicators
            source_phrases = repo.get_source_indicators()
            if source_phrases:
                self._source_indicators = source_phrases
                loaded_any = True
            
            # Load scoring config
            scoring = repo.get_scoring_config()
            if scoring:
                self._scoring_config = scoring
                loaded_any = True
            
            # Load date patterns
            date_pats = repo.get_date_patterns()
            if date_pats:
                self._date_patterns = date_pats
                loaded_any = True
            
            if loaded_any:
                self._loaded = True
                logger.info("[VALIDATOR] Validation rules loaded from MongoDB")
                return True
            else:
                logger.warning("[VALIDATOR] No validation rules found in MongoDB")
                return False
            
        except Exception as e:
            logger.warning(f"[VALIDATOR] MongoDB unavailable, using defaults: {e}")
            return False
    
    def load_defaults(self):
        """Load hardcoded default values as fallback."""
        # Common English stopwords
        self._stopwords = frozenset({
            "a", "about", "above", "after", "again", "against", "all", "am", "an",
            "and", "any", "are", "aren't", "as", "at", "be", "because", "been",
            "before", "being", "below", "between", "both", "but", "by", "can",
            "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
            "doesn't", "doing", "don", "don't", "down", "during", "each", "few",
            "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
            "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
            "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
            "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't",
            "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't",
            "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
            "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
            "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't",
            "so", "some", "such", "than", "that", "that's", "the", "their", "theirs",
            "them", "themselves", "then", "there", "there's", "these", "they",
            "they'd", "they'll", "they're", "they've", "this", "those", "through",
            "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
            "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's",
            "when", "when's", "where", "where's", "which", "while", "who", "who's",
            "whom", "why", "why's", "will", "with", "won't", "would", "wouldn't",
            "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself",
            "yourselves",
        })
        
        # Sensationalist word patterns (fake news indicators)
        self._sensationalist_words = frozenset({
            "shocking", "unbelievable", "miracle", "exposed", "cover-up", "hoax",
            "conspiracy", "secret", "hidden", "they don't want you to know",
            "mainstream media", "lying", "fake", "scam", "fraud", "bombshell",
            "breaking", "exclusive", "leaked",
        })
        
        # Source indicator phrases
        self._source_indicators = [
            "according to", "said", "reported", "stated",
            "announced", "official", "government", "study",
        ]
        
        # Scoring configuration
        self._scoring_config = {
            "base_score": 0.5,
            "sensationalist_weight": -0.1,
            "caps_words_threshold": 3,
            "caps_words_penalty": -0.15,
            "exclamation_threshold": 2,
            "exclamation_weight": -0.05,
            "question_mark_threshold": 1,
            "question_mark_weight": -0.03,
            "source_indicator_weight": 0.15,
            "numeric_data_weight": 0.1,
            "date_pattern_weight": 0.05,
            "min_score": 0.01,
            "max_score": 0.99,
            "real_news_threshold": 0.45,
        }
        
        # Date patterns
        self._date_patterns = [
            r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        ]
        
        self._loaded = True
        logger.info("[VALIDATOR] Validation rules loaded from defaults")
    
    @classmethod
    def ensure_loaded(cls):
        """Ensure rules are loaded (try MongoDB first, fallback to defaults)."""
        instance = cls.get_instance()
        if not instance._loaded:
            if not instance.load_from_mongodb():
                instance.load_defaults()
        return instance
    
    def _ensure_instance_loaded(self):
        """Ensure this instance has rules loaded."""
        if not self._loaded:
            logger.debug("[VALIDATOR] Loading validation rules...")
            if not self.load_from_mongodb():
                logger.debug("[VALIDATOR] Falling back to default rules")
                self.load_defaults()
    
    @property
    def stopwords(self) -> frozenset:
        self._ensure_instance_loaded()
        return self._stopwords
    
    @property
    def sensationalist_words(self) -> frozenset:
        self._ensure_instance_loaded()
        return self._sensationalist_words
    
    @property
    def source_indicators(self) -> List[str]:
        self._ensure_instance_loaded()
        return self._source_indicators
    
    @property
    def scoring_config(self) -> dict:
        self._ensure_instance_loaded()
        return self._scoring_config
    
    @property
    def date_patterns(self) -> List[str]:
        self._ensure_instance_loaded()
        return self._date_patterns


def get_validation_rules() -> ValidationRulesCache:
    """Get validation rules instance."""
    return ValidationRulesCache.get_instance()


def preprocess_text(text: str) -> str:
    """Lightweight text cleaning without external NLP libraries."""
    rules = get_validation_rules()
    
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\d+", "", text)
    tokens = [
        t for t in text.split()
        if t not in rules.stopwords and len(t) > 2
    ]
    return " ".join(tokens)


def heuristic_predict(text: str) -> Tuple[bool, float]:
    """
    Rule-based prediction. Returns (is_real, confidence).
    Confidence is 0.0-1.0 (higher = more confident).
    """
    rules = get_validation_rules()
    config = rules.scoring_config
    
    text_lower = text.lower()
    score = config["base_score"]

    # Sensationalist words penalty
    sens_count = sum(1 for w in rules.sensationalist_words if w in text_lower)
    if sens_count > 0:
        score += sens_count * config["sensationalist_weight"]

    # ALL CAPS words penalty
    caps_words = re.findall(r'\b[A-Z]{3,}\b', text)
    if len(caps_words) > config["caps_words_threshold"]:
        score += config["caps_words_penalty"]

    # Exclamation marks penalty
    excl_count = text.count("!")
    if excl_count > config["exclamation_threshold"]:
        score += excl_count * config["exclamation_weight"]

    # Question marks penalty
    qmark_count = text.count("?")
    if qmark_count > config["question_mark_threshold"]:
        score += qmark_count * config["question_mark_weight"]

    # Source indicators bonus
    if any(w in text_lower for w in rules.source_indicators):
        score += config["source_indicator_weight"]

    # Numeric data bonus
    if re.search(r"\d+\.?\d*\s*(percent|billion|million|thousand|%)", text_lower):
        score += config["numeric_data_weight"]

    # Date patterns bonus
    for pattern in rules.date_patterns:
        if re.search(pattern, text_lower):
            score += config["date_pattern_weight"]
            break

    # Clamp score
    score = max(config["min_score"], min(config["max_score"], score))
    
    # Determine if real and confidence
    is_real = score >= config["real_news_threshold"]
    confidence = abs(score - 0.5) * 2
    return is_real, confidence

