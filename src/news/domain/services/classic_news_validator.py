"""
Classic Fake News Validator — domain logic only.

Pure heuristic rules for news validation. No infrastructure dependencies.
Configuration is injected or uses hardcoded defaults.
"""

import re
import string
from typing import Tuple, Optional, List


class ValidationRulesCache:
    """Cache for validation rules. Pure domain logic — no infrastructure deps."""

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
            cls._instance.load_defaults()
        return cls._instance

    def load_from_mongodb(self) -> bool:
        """
        Stub: MongoDB loading moved to infrastructure layer.
        Infrastructure should inject rules via load_rules() method.
        """
        return False

    def load_rules(self, rules: dict) -> None:
        """
        Load validation rules from external source (infrastructure).
        This keeps the domain pure while allowing external configuration.

        Args:
            rules: Dict with keys: stopwords, sensationalist_words,
                   source_indicators, scoring_config, date_patterns
        """
        if "stopwords" in rules and rules["stopwords"]:
            self._stopwords = frozenset(rules["stopwords"])
        if "sensationalist_words" in rules and rules["sensationalist_words"]:
            self._sensationalist_words = frozenset(rules["sensationalist_words"])
        if "source_indicators" in rules and rules["source_indicators"]:
            self._source_indicators = rules["source_indicators"]
        if "scoring_config" in rules and rules["scoring_config"]:
            self._scoring_config = rules["scoring_config"]
        if "date_patterns" in rules and rules["date_patterns"]:
            self._date_patterns = rules["date_patterns"]
        self._loaded = True

    def load_defaults(self):
        """Load hardcoded default values."""
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

        self._sensationalist_words = frozenset({
            "shocking", "unbelievable", "miracle", "exposed", "cover-up", "hoax",
            "conspiracy", "secret", "hidden", "they don't want you to know",
            "mainstream media", "lying", "fake", "scam", "fraud", "bombshell",
            "breaking", "exclusive", "leaked",
        })

        self._source_indicators = [
            "according to", "said", "reported", "stated",
            "announced", "official", "government", "study",
        ]

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

        self._date_patterns = [
            r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
            r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        ]

        self._loaded = True

    @property
    def stopwords(self) -> frozenset:
        if not self._loaded:
            self.load_defaults()
        return self._stopwords

    @property
    def sensationalist_words(self) -> frozenset:
        if not self._loaded:
            self.load_defaults()
        return self._sensationalist_words

    @property
    def source_indicators(self) -> List[str]:
        if not self._loaded:
            self.load_defaults()
        return self._source_indicators

    @property
    def scoring_config(self) -> dict:
        if not self._loaded:
            self.load_defaults()
        return self._scoring_config

    @property
    def date_patterns(self) -> List[str]:
        if not self._loaded:
            self.load_defaults()
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

