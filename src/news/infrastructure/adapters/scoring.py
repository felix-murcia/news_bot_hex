import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from config.logging_config import get_logger

logger = get_logger("news_bot.infra.news_adapters")


_STOP_WORDS = frozenset({
    "el", "la", "los", "las", "de", "del", "en", "un", "una", "por", "para",
    "con", "su", "sus", "al", "se", "es", "y", "o", "que", "a", "no", "the",
    "of", "in", "to", "and", "is", "for", "on", "at", "an", "as", "its",
})


def _title_keywords(title: str) -> set:
    words = set(re.findall(r"\w+", title.lower()))
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def _jaccard_similarity(title_a: str, title_b: str) -> float:
    words_a = _title_keywords(title_a)
    words_b = _title_keywords(title_b)
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def deduplicate_by_similarity(articles: List[Dict], threshold: float = 0.35) -> List[Dict]:
    """Group articles covering the same story and keep only the highest-scored one per group."""
    if len(articles) <= 1:
        return articles

    used = set()
    result = []
    deduplicated_count = 0

    for i in range(len(articles)):
        if i in used:
            continue
        group = [i]
        used.add(i)
        for j in range(i + 1, len(articles)):
            if j in used:
                continue
            sim = _jaccard_similarity(
                articles[i].get("title", ""),
                articles[j].get("title", ""),
            )
            if sim >= threshold:
                group.append(j)
                used.add(j)

        best_idx = max(group, key=lambda idx: int(articles[idx].get("score", 0)))
        result.append(articles[best_idx])
        if len(group) > 1:
            deduplicated_count += len(group) - 1

    logger.info(
        f"[DEDUP] {len(articles)} artículos → {len(result)} únicos "
        f"({deduplicated_count} duplicados eliminados)"
    )
    return result


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
            if dt > datetime.utcnow() - timedelta(hours=24):
                score += 2
            elif dt > datetime.utcnow() - timedelta(days=3):
                score += 1
        except Exception:
            pass
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


def categorizar_noticia(title: str, desc: str) -> str:
    try:
        from src.shared.adapters.categorizacion import etiquetar_tematica

        return etiquetar_tematica(title, desc)
    except Exception:
        return "Noticias"


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
