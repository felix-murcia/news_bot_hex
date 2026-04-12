"""
Default Validation Rules for News Validator.

This file contains the default validation rules that can be seeded into MongoDB.
These rules replace the hardcoded values in classic_news_validator.py.
"""

DEFAULT_VALIDATION_RULES = {
    # English stopwords
    "stopwords_english": {
        "_id": "stopwords_english",
        "language": "english",
        "description": "Common English stopwords for text preprocessing",
        "words": [
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
        ],
    },
    
    # Spanish stopwords
    "stopwords_spanish": {
        "_id": "stopwords_spanish",
        "language": "spanish",
        "description": "Common Spanish stopwords for text preprocessing",
        "words": [
            "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
            "en", "y", "o", "que", "es", "son", "ser", "estar", "está", "están",
            "por", "para", "con", "sin", "se", "su", "sus", "al", "lo", "le",
            "les", "como", "más", "pero", "este", "esta", "estos", "estas", "ese",
            "esa", "esos", "esas", "todo", "todos", "todas", "ya", "muy", "también",
            "no", "si", "cuando", "donde", "quien", "cual", "cuyo", "sus", "tu",
            "tus", "mi", "mis", "me", "te", "nos", "os", "le", "les", "se",
        ],
    },
    
    # Sensationalist words (fake news indicators)
    "sensationalist_default": {
        "_id": "sensationalist_default",
        "description": "Sensationalist word patterns that indicate fake news",
        "weight": -0.1,
        "max_penalty": -0.5,
        "words": [
            "shocking", "unbelievable", "miracle", "exposed", "cover-up", "hoax",
            "conspiracy", "secret", "hidden", "they don't want you to know",
            "mainstream media", "lying", "fake", "scam", "fraud", "bombshell",
            "breaking", "exclusive", "leaked",
            # Spanish sensationalist words
            "impactante", "increíble", "milagro", "destapado", "encubrimiento",
            "engaño", "conspiración", "secreto", "oculto", "no quieren que sepas",
            "medios tradicionales", "mintiendo", "falso", "estafa", "fraude",
            "bomba", "última hora", "exclusiva", "filtrado", "escandaloso",
        ],
    },
    
    # Source indicators (credibility boosters)
    "source_indicators_default": {
        "_id": "source_indicators_default",
        "description": "Phrases that indicate credible sourcing",
        "weight": 0.15,
        "phrases": [
            "according to", "said", "reported", "stated",
            "announced", "official", "government", "study",
            # Spanish source indicators
            "según", "dijo", "reportó", "declaró", "afirmó",
            "anunció", "oficial", "gobierno", "estudio", "investigación",
        ],
    },
    
    # Scoring configuration
    "scoring_default": {
        "_id": "scoring_default",
        "description": "Scoring configuration for news validation",
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
    },
    
    # Date patterns (credibility boosters)
    "date_patterns_default": {
        "_id": "date_patterns_default",
        "description": "Date and time patterns that increase credibility",
        "weight": 0.05,
        "patterns": [
            r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b",
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            # Spanish date patterns
            r"\b(lunes|martes|miércoles|jueves|viernes|sábado|domingo)\b",
            r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b",
        ],
    },
}


def seed_validation_rules(repository) -> bool:
    """
    Seed the MongoDB collection with default validation rules.
    
    Args:
        repository: MongoValidationRulesRepository instance
        
    Returns:
        True if all rules were seeded successfully
    """
    success = True
    for rule_id, rules in DEFAULT_VALIDATION_RULES.items():
        if not repository.save_rules(rule_id, rules):
            success = False
    return success
