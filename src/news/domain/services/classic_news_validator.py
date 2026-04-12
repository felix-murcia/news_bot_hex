"""
Classic Fake News Validator — domain logic only.

Pure heuristic rules for news validation. No external dependencies.
ML model loading lives in the infrastructure adapter.
"""

import re
import string
from typing import Tuple


# Common English stopwords
_STOPWORDS = frozenset({
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
_SENSATIONALIST_WORDS = frozenset({
    "shocking", "unbelievable", "miracle", "exposed", "cover-up", "hoax",
    "conspiracy", "secret", "hidden", "they don't want you to know",
    "mainstream media", "lying", "fake", "scam", "fraud", "bombshell",
    "breaking", "exclusive", "leaked",
})


def preprocess_text(text: str) -> str:
    """Lightweight text cleaning without external NLP libraries."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\d+", "", text)
    tokens = [
        t for t in text.split()
        if t not in _STOPWORDS and len(t) > 2
    ]
    return " ".join(tokens)


def heuristic_predict(text: str) -> Tuple[bool, float]:
    """
    Rule-based prediction. Returns (is_real, confidence).
    Confidence is 0.0-1.0 (higher = more confident).
    """
    text_lower = text.lower()
    score = 0.5

    sens_count = sum(1 for w in _SENSATIONALIST_WORDS if w in text_lower)
    if sens_count > 0:
        score -= sens_count * 0.1

    caps_words = re.findall(r'\b[A-Z]{3,}\b', text)
    if len(caps_words) > 3:
        score -= 0.15

    excl_count = text.count("!")
    if excl_count > 2:
        score -= excl_count * 0.05

    qmark_count = text.count("?")
    if qmark_count > 1:
        score -= qmark_count * 0.03

    source_words = ["according to", "said", "reported", "stated",
                    "announced", "official", "government", "study"]
    if any(w in text_lower for w in source_words):
        score += 0.15

    if re.search(r"\d+\.?\d*\s*(percent|billion|million|thousand|%)", text_lower):
        score += 0.1

    if re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text_lower):
        score += 0.05

    score = max(0.01, min(0.99, score))
    is_real = score >= 0.45
    confidence = abs(score - 0.5) * 2
    return is_real, confidence
