"""
Default Validation Rules for News Validator.

This file contains the default validation rules that can be seeded into MongoDB.
These rules replace the hardcoded values in classic_news_validator.py.
"""

from collections import Counter
import re
from typing import Optional

from config.logging_config import get_logger

logger = get_logger("news_bot")


DEFAULT_VALIDATION_RULES = {
    # English stopwords
    "stopwords_english": {
        "_id": "stopwords_english",
        "language": "english",
        "description": "Common English stopwords for text preprocessing",
        "words": [
            "a",
            "about",
            "above",
            "after",
            "again",
            "against",
            "all",
            "am",
            "an",
            "and",
            "any",
            "are",
            "aren't",
            "as",
            "at",
            "be",
            "because",
            "been",
            "before",
            "being",
            "below",
            "between",
            "both",
            "but",
            "by",
            "can",
            "can't",
            "cannot",
            "could",
            "couldn't",
            "did",
            "didn't",
            "do",
            "does",
            "doesn't",
            "doing",
            "don",
            "don't",
            "down",
            "during",
            "each",
            "few",
            "for",
            "from",
            "further",
            "had",
            "hadn't",
            "has",
            "hasn't",
            "have",
            "haven't",
            "having",
            "he",
            "he'd",
            "he'll",
            "he's",
            "her",
            "here",
            "here's",
            "hers",
            "herself",
            "him",
            "himself",
            "his",
            "how",
            "how's",
            "i",
            "i'd",
            "i'll",
            "i'm",
            "i've",
            "if",
            "in",
            "into",
            "is",
            "isn't",
            "it",
            "it's",
            "its",
            "itself",
            "let's",
            "me",
            "more",
            "most",
            "mustn't",
            "my",
            "myself",
            "no",
            "nor",
            "not",
            "of",
            "off",
            "on",
            "once",
            "only",
            "or",
            "other",
            "ought",
            "our",
            "ours",
            "ourselves",
            "out",
            "over",
            "own",
            "same",
            "shan't",
            "she",
            "she'd",
            "she'll",
            "she's",
            "should",
            "shouldn't",
            "so",
            "some",
            "such",
            "than",
            "that",
            "that's",
            "the",
            "their",
            "theirs",
            "them",
            "themselves",
            "then",
            "there",
            "there's",
            "these",
            "they",
            "they'd",
            "they'll",
            "they're",
            "they've",
            "this",
            "those",
            "through",
            "to",
            "too",
            "under",
            "until",
            "up",
            "very",
            "was",
            "wasn't",
            "we",
            "we'd",
            "we'll",
            "we're",
            "we've",
            "were",
            "weren't",
            "what",
            "what's",
            "when",
            "when's",
            "where",
            "where's",
            "which",
            "while",
            "who",
            "who's",
            "whom",
            "why",
            "why's",
            "will",
            "with",
            "won't",
            "would",
            "wouldn't",
            "you",
            "you'd",
            "you'll",
            "you're",
            "you've",
            "your",
            "yours",
            "yourself",
            "yourselves",
        ],
    },
    # Spanish stopwords
    "stopwords_spanish": {
        "_id": "stopwords_spanish",
        "language": "spanish",
        "description": "Common Spanish stopwords for text preprocessing",
        "words": [
            "el",
            "la",
            "los",
            "las",
            "un",
            "una",
            "unos",
            "unas",
            "de",
            "del",
            "en",
            "y",
            "o",
            "que",
            "es",
            "son",
            "ser",
            "estar",
            "está",
            "están",
            "por",
            "para",
            "con",
            "sin",
            "se",
            "su",
            "sus",
            "al",
            "lo",
            "le",
            "les",
            "como",
            "más",
            "pero",
            "este",
            "esta",
            "estos",
            "estas",
            "ese",
            "esa",
            "esos",
            "esas",
            "todo",
            "todos",
            "todas",
            "ya",
            "muy",
            "también",
            "no",
            "si",
            "cuando",
            "donde",
            "quien",
            "cual",
            "cuyo",
            "sus",
            "tu",
            "tus",
            "mi",
            "mis",
            "me",
            "te",
            "nos",
            "os",
            "le",
            "les",
            "se",
        ],
    },
    # Sensationalist words (fake news indicators)
    "sensationalist_default": {
        "_id": "sensationalist_default",
        "description": "Sensationalist word patterns that indicate fake news",
        "weight": -0.1,
        "max_penalty": -0.5,
        "words": [
            "shocking",
            "unbelievable",
            "miracle",
            "exposed",
            "cover-up",
            "hoax",
            "conspiracy",
            "secret",
            "hidden",
            "they don't want you to know",
            "mainstream media",
            "lying",
            "fake",
            "scam",
            "fraud",
            "bombshell",
            "breaking",
            "exclusive",
            "leaked",
            # Spanish sensationalist words
            "impactante",
            "increíble",
            "milagro",
            "destapado",
            "encubrimiento",
            "engaño",
            "conspiración",
            "secreto",
            "oculto",
            "no quieren que sepas",
            "medios tradicionales",
            "mintiendo",
            "falso",
            "estafa",
            "fraude",
            "bomba",
            "última hora",
            "exclusiva",
            "filtrado",
            "escandaloso",
        ],
    },
    # Source indicators (credibility boosters)
    "source_indicators_default": {
        "_id": "source_indicators_default",
        "description": "Phrases that indicate credible sourcing",
        "weight": 0.15,
        "phrases": [
            "according to",
            "said",
            "reported",
            "stated",
            "announced",
            "official",
            "government",
            "study",
            # Spanish source indicators
            "según",
            "dijo",
            "reportó",
            "declaró",
            "afirmó",
            "anunció",
            "oficial",
            "gobierno",
            "estudio",
            "investigación",
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


class ImageRelevanceValidator:
    """
    Valida la relevancia visual de imágenes respecto a un artículo.
    Incluye caché de keywords y scores para optimización.
    """

    # Conjunto de palabras visuales comunes (eventos, lugares, objetos recognizables)
    VISUAL_KEYWORDS = {
        # Eventos visuales
        "protesta",
        "manifestación",
        "marcha",
        "reunión",
        "cumbre",
        "conferencia",
        "ataque",
        "guerra",
        "conflicto",
        "bombardeo",
        "explosión",
        "batalla",
        "terremoto",
        "inundación",
        "incendio",
        "tormenta",
        "huracán",
        "tsunami",
        "elección",
        "elecciones",
        "debate",
        "votación",
        "campaña",
        # Lugares visualmente reconocibles
        "hospital",
        "escuela",
        "universidad",
        "iglesia",
        "catedral",
        "mezquita",
        "estadio",
        "puerto",
        "aeropuerto",
        "estación",
        "plaza",
        "calle",
        "edificio",
        "rascacielos",
        "puente",
        "carretera",
        # Objetos/entes visuales
        "refinería",
        "fábrica",
        "tanque",
        "misil",
        "cohete",
        "avión",
        "barco",
        "submarino",
        "helicóptero",
        "vehículo",
        "camión",
        "presidente",
        "ministro",
        "general",
        "líder",
        "papa",
        "obispo",
        "persona",
        "gente",
        "multitud",
        "manifestante",
        "soldado",
        "policía",
        "bombero",
        "paramédico",
        # Naturaleza
        "montaña",
        "río",
        "mar",
        "océano",
        "bosque",
        "desierto",
        "volcán",
        "nieve",
        "hielo",
        "playa",
        "costa",
    }

    # Patrón regex para detectar nombres propios (palabras con mayúscula inicial)
    PROPER_NOUN_PATTERN = r"\b[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]{2,}\b"

    # Stopwords comunes en español e inglés para filtrar palabras irrelevantes
    STOPWORDS = {
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "de",
        "del",
        "en",
        "y",
        "o",
        "que",
        "es",
        "son",
        "se",
        "con",
        "por",
        "para",
        "sin",
        "sobre",
        "entre",
        "hacia",
        "desde",
        "esta",
        "este",
        "estos",
        "estas",
        "ese",
        "esa",
        "esos",
        "esas",
        "aquel",
        "aquella",
        "como",
        "cuando",
        "donde",
        "más",
        "pero",
        "si",
        "no",
        "ya",
        "muy",
        "todo",
        "todos",
        "al",
        "lo",
        "le",
        "les",
        "su",
        "sus",
        "ser",
        "estar",
        "hay",
        "tener",
        "hacer",
        "decir",
        "poder",
        "deber",
        "querer",
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "shall",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "not",
    }

    # Caché para no recalcular keywords del mismo artículo
    _keyword_cache: dict[str, list[str]] = {}

    # Caché para scores de imágenes (descripción + texto)
    _score_cache: dict[str, float] = {}

    def reset_cache(self):
        """Limpia los cachés (útil para tests o nuevo ciclo)."""
        self._keyword_cache.clear()
        self._score_cache.clear()

    def _get_cache_key(self, article_text: str) -> str:
        """Genera una clave de caché a partir del texto del artículo."""
        return article_text[:200].strip().lower()

    def extract_visual_keywords(
        self,
        article_text: str,
        article_title: str,
        fallback_category: Optional[str] = None,
    ) -> list[str]:
        """
        Extrae keywords visuales relevantes del artículo.
        Prioriza: nombres propios > eventos > lugares > objetos comunes.
        Retorna lista de 3-5 keywords.

        Args:
            article_text: texto completo del artículo
            article_title: título del artículo
            fallback_category: categoría/tema a usar si no se extraen keywords suficientes
        """
        cache_key = self._get_cache_key(article_title + " " + article_text)
        if cache_key in self._keyword_cache:
            return self._keyword_cache[cache_key]

        keywords = []
        combined = f"{article_title} {article_text[:500]}"
        text_lower = combined.lower()

        # 1. Extraer nombres propios
        proper_nouns = re.findall(self.PROPER_NOUN_PATTERN, combined)
        proper_nouns = [
            np
            for np in proper_nouns
            if len(np) > 2 and np.lower() not in self.STOPWORDS
        ]
        keywords.extend(proper_nouns[:2])

        # 2. Buscar palabras visuales conocidas
        for visual_word in self.VISUAL_KEYWORDS:
            if visual_word in text_lower and visual_word not in keywords:
                keywords.append(visual_word)
                if len(keywords) >= 4:
                    break

        # 3. Si faltan keywords, extraer palabras significativas (4+ letras)
        if len(keywords) < 3:
            words = re.findall(r"\b[a-záéíóúñü]{4,}\b", text_lower)
            filtered = [w for w in words if w not in self.STOPWORDS]
            for word in filtered:
                if word not in keywords:
                    keywords.append(word)
                if len(keywords) >= 5:
                    break

        # 4. Fallback con categoría si aún no hay suficientes keywords
        if len(keywords) < 2 and fallback_category:
            cat_lower = fallback_category.lower()
            if cat_lower not in [k.lower() for k in keywords]:
                keywords.append(fallback_category.capitalize())

        # 5. Eliminar duplicados manteniendo orden y limitar a 5
        seen = set()
        unique_keywords = []
        for k in keywords:
            if k.lower() not in seen:
                seen.add(k.lower())
                unique_keywords.append(k)

        result = unique_keywords[:5]
        self._keyword_cache[cache_key] = result

        logger.debug(
            f"[VALIDATOR] Extraídas keywords: {result} para artículo '{article_title[:30]}...'"
        )

        return result

    def calculate_relevance_score(
        self, image_description: str, article_text: str
    ) -> float:
        """
        Calcula similitud semántica entre imagen y artículo.
        Retorna un score entre 0 y 1.

        Usa caché para evitar recalcular el mismo par.
        """
        if not image_description or not article_text:
            return 0.0

        cache_key = f"{image_description[:100]}|||{article_text[:200]}".lower()
        if cache_key in self._score_cache:
            return self._score_cache[cache_key]

        desc_lower = image_description.lower()
        text_lower = article_text.lower()

        desc_words = set(re.findall(r"\b[a-záéíóúñü]{4,}\b", desc_lower))
        desc_words = {w for w in desc_words if w not in self.STOPWORDS}

        article_words = set(re.findall(r"\b[a-záéíóúñü]{4,}\b", text_lower))
        article_words = {w for w in article_words if w not in self.STOPWORDS}

        if not desc_words or not article_words:
            self._score_cache[cache_key] = 0.0
            return 0.0

        common_words = desc_words.intersection(article_words)
        union_size = len(desc_words.union(article_words))
        if union_size == 0:
            self._score_cache[cache_key] = 0.0
            return 0.0

        jaccard_score = len(common_words) / union_size

        visual_bonus = sum(0.1 for word in common_words if word in self.VISUAL_KEYWORDS)

        final_score = min(jaccard_score + visual_bonus, 1.0)

        self._score_cache[cache_key] = final_score
        return final_score
