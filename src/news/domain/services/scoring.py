import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List

logger = logging.getLogger(__name__)

_STOP_WORDS = frozenset({
    "el", "la", "los", "las", "de", "del", "en", "un", "una", "por", "para",
    "con", "su", "sus", "al", "se", "es", "y", "o", "que", "a", "no", "the",
    "of", "in", "to", "and", "is", "for", "on", "at", "an", "as", "its",
})


def _normalize_title(title: str) -> str:
    """Normaliza un título para detección de duplicados: minúsculas, sin puntuación."""
    return re.sub(r"[^\w\s]", "", title.lower()).strip()


def deduplicate_by_similarity(articles: List[Dict], threshold: float = 0.35) -> List[Dict]:
    """Elimina duplicados por título normalizado en O(n) usando un HashSet.

    Reemplaza el doble bucle O(n²) (comparaciones cruzadas) por una pasada lineal.
    threshold se conserva por compatibilidad de firma pero ya no se usa: el Set
    de títulos normalizados elimina duplicados exactos/casi-exactos sin coste.
    """
    seen_hashes = set()
    unique_articles = []
    for art in articles:
        norm = _normalize_title(art.get("title", ""))
        if norm and norm not in seen_hashes:
            seen_hashes.add(norm)
            unique_articles.append(art)

    logger.info(
        f"[DEDUP] {len(articles)} artículos → {len(unique_articles)} únicos "
        f"(O(n) HashSet, {len(articles) - len(unique_articles)} duplicados eliminados)"
    )
    return unique_articles


def apply_diversity_penalty(
    articles: List[Dict],
    recent_topics: Dict[str, int],
    penalty_per_occurrence: int = 3,
    max_penalty: int = 8,
) -> List[Dict]:
    """Penalize articles from topics that were recently published to promote variety."""
    if not recent_topics:
        return articles

    penalized = 0
    for article in articles:
        tema = article.get("tema", "")
        if tema in recent_topics:
            count = recent_topics[tema]
            penalty = min(max_penalty, penalty_per_occurrence * count)
            original_score = int(article.get("score", 0))
            article["score"] = max(0, original_score - penalty)
            article["diversity_penalty"] = penalty
            penalized += 1

    logger.info(
        f"[DIVERSITY] {penalized} artículos penalizados por tema reciente. "
        f"Temas recientes: {recent_topics}"
    )
    return articles


def apply_frozen_terms_penalty(
    articles: List[Dict],
    frozen_terms: List[str],
    penalty_per_match: int = 2,
    max_penalty: int = 10,
) -> List[Dict]:
    """Penalize articles containing recently frozen terms."""
    if not frozen_terms:
        return articles

    frozen_lower = [t.lower() for t in frozen_terms]
    penalized = 0

    for article in articles:
        text = f"{article.get('title', '')} {article.get('desc', '')}".lower()
        matches = [t for t in frozen_lower if t in text]
        if matches:
            penalty = min(max_penalty, penalty_per_match * len(matches))
            original_score = int(article.get("score", 0))
            article["score"] = max(0, original_score - penalty)
            article["frozen_penalty"] = penalty
            article["frozen_matches"] = matches
            penalized += 1

    logger.info(
        f"[FROZEN] {penalized} artículos penalizados por términos congelados. "
        f"Términos activos: {frozen_terms}"
    )
    return articles


def compute_score(
    article: dict,
    tema: str,
    confidence: float,
    scoring_rules: dict,
    source_prioritarias: set,
    trending_keywords: list,
    breaking_keywords: list,
    weights: dict,
) -> int:
    score = scoring_rules.get(tema, 0)
    pub = article.get("publishedAt")
    if pub:
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if dt > now - timedelta(hours=24):
                score += 2
            elif dt > now - timedelta(days=3):
                score += 1
        except Exception as e:
            logger.error(f"[SCORING] publishedAt inválido: {pub!r}: {e}")
            raise
    source = article.get("source")
    source_name = (
        source.get("name", "") if isinstance(source, dict) else str(source or "")
    )
    if source_name in source_prioritarias:
        score += 2
    if confidence > 0.9:
        score += 1
    text = f"{article.get('title', '')} {article.get('desc', '')}".lower()
    matched_trends = [t for t in trending_keywords if t and t in text]
    if matched_trends:
        score += min(
            weights.get("max_trending_bonus", 3),
            len(matched_trends) * weights.get("trending_weight", 1),
        )
    matched_breaking = [kw for kw in breaking_keywords if kw and kw in text]
    if matched_breaking:
        score += min(
            weights.get("max_breaking_bonus", 4),
            len(matched_breaking) * weights.get("breaking_weight", 2),
        )
    return score


def check_breaking_keywords(title: str, desc: str, breaking_keywords: List[str]) -> int:
    text = f"{title} {desc}".lower()
    tokens = set(re.findall(r"\b\w+\b", text))
    return sum(
        1
        for kw in breaking_keywords
        if any(word in tokens for word in kw.lower().split())
    )


def is_valid_score(
    score: float, breaking_hits: int, min_score_threshold: int = 5
) -> bool:
    return score > min_score_threshold or breaking_hits > 2


def sort_verified_news(news_list: List[Dict]) -> List[Dict]:
    def sort_key(item):
        return (
            int(item.get("score", 0)),
            parse_iso_date(item.get("publishedAt") or ""),
        )

    return sorted(news_list, key=sort_key, reverse=True)


def parse_iso_date(date_str: str) -> datetime:
    if not date_str:
        return datetime.min
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.min


def resumir_noticia(title: str, desc: str) -> str:
    resumen = f"{title.strip()}. {desc.strip()}" if desc else title.strip()
    return (resumen[:247] + "...") if len(resumen) > 250 else resumen
