import re
from typing import Dict
from config.logging_config import get_logger

logger = get_logger("news_bot")

KEYWORDS = None
CATEGORIES = ["Noticias"]

SHORT_TOKENS = {
    "Seguridad": ["ai"],
    "Economía": ["gdp"],
    "Tecnología": ["ai", "app", "tv", "vr", "ar"],
    "Deportes": ["ufc", "f1", "nba", "mlb", "nhl"],
}

SHORT_PATTERNS = {
    cat: [re.compile(rf"\b{re.escape(tok)}\b", flags=re.IGNORECASE) for tok in toks]
    for cat, toks in SHORT_TOKENS.items()
}


def _ensure_keywords_loaded():
    global KEYWORDS, CATEGORIES
    if KEYWORDS is None:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["keywords"]
            data = coll.find_one({})
            if data:
                data.pop("_id", None)
                if data:
                    KEYWORDS = data
                    CATEGORIES = list(KEYWORDS.keys()) + ["Noticias"]
                else:
                    KEYWORDS = {}
                    CATEGORIES = ["Noticias"]
                    logger.warning("[CATEGORIZACIÓN] No hay keywords en MongoDB")
            else:
                KEYWORDS = {}
                CATEGORIES = ["Noticias"]
                logger.warning("[CATEGORIZACIÓN] No hay keywords en MongoDB")
        except Exception as e:
            logger.error(f"[CATEGORIZACIÓN] Error cargando keywords: {e}")
            KEYWORDS = {}
            CATEGORIES = ["Noticias"]


def etiquetar_tematica(title: str, desc: str, model=None) -> str:
    _ensure_keywords_loaded()

    if not KEYWORDS:
        return "Noticias"

    texto = f"{title} {desc}".lower()
    scores = {cat: 0 for cat in KEYWORDS.keys()}

    for categoria, patterns in SHORT_PATTERNS.items():
        for pat in patterns:
            if pat.search(texto):
                scores[categoria] += 3

    for categoria, palabras in KEYWORDS.items():
        for k in palabras:
            if len(k) <= 3:
                if re.search(rf"\b{re.escape(k)}\b", texto, flags=re.IGNORECASE):
                    scores[categoria] += 1
            else:
                if k.lower() in texto:
                    scores[categoria] += 1

    best_cat = max(scores, key=lambda c: scores[c])
    if scores[best_cat] > 0:
        logger.info(
            f"[CATEGORIZACIÓN] '{title}' → {best_cat} (score={scores[best_cat]})"
        )
        return best_cat

    if model:
        prompt = f"Clasifica la siguiente noticia en una de estas categorías: {', '.join(CATEGORIES)}.\n\nTítulo: {title}\nDescripción: {desc}\n\nDevuelve solo el nombre de la categoría."
        try:
            respuesta = model(prompt).strip()
            if respuesta in CATEGORIES:
                logger.info(f"[CATEGORIZACIÓN] '{title}' → {respuesta} (modelo)")
                return respuesta
            return "Noticias"
        except Exception as e:
            logger.error(f"[CATEGORIZACIÓN] Error consultando modelo: {e}")
            return "Noticias"

    logger.info(f"[CATEGORIZACIÓN] '{title}' → Noticias (fallback)")
    return "Noticias"


def reload_keywords():
    global KEYWORDS, CATEGORIES
    _ensure_keywords_loaded()
    logger.info(
        f"[CATEGORIZACIÓN] Keywords recargadas: {len(KEYWORDS) if KEYWORDS else 0} categorías"
    )
