import logging
import re
from typing import List

from src.news.domain.services.scoring import (
    _STOP_WORDS,
    apply_diversity_penalty,
    apply_frozen_terms_penalty,
    check_breaking_keywords,
    compute_score,
    deduplicate_by_similarity,
    is_valid_score,
    parse_iso_date,
    resumir_noticia,
    sort_verified_news,
)

logger = logging.getLogger(__name__)

_FROZEN_TERMS_PROMPT = (
    "Extract 3 to 5 key named entities (countries, people, organizations, "
    "specific places) from this news headline. Return ONLY a comma-separated "
    "list of the entities, nothing else. Example: Irán, Trump, Anthropic\n\n"
    "Headline: {title}"
)


def extract_frozen_terms(title: str) -> List[str]:
    """Extract key named entities from a title using LLM."""
    try:
        from src.shared.adapters.ai.ai_factory import get_ai_adapter
        model = get_ai_adapter()
        raw = model.generate(
            prompt=_FROZEN_TERMS_PROMPT.format(title=title),
            temperature=0.0,
            max_tokens=64,
        )
        terms = [t.strip() for t in raw.strip().split(",") if t.strip()]
        terms = [t for t in terms if 2 < len(t) < 40]
        logger.info(f"[FROZEN] Extracted terms from '{title[:50]}': {terms}")
        return terms
    except Exception as e:
        logger.warning(f"[FROZEN] LLM extraction failed, using fallback: {e}")
        return _extract_frozen_terms_fallback(title)


def _extract_frozen_terms_fallback(title: str) -> List[str]:
    """Fallback: extract capitalized words that look like proper nouns."""
    words = re.findall(r"\w+", title)
    terms = []
    for word in words:
        if len(word) <= 2 or word.lower() in _STOP_WORDS:
            continue
        if word[0].isupper() and not word.isupper():
            terms.append(word)
    return terms[:5]


def categorizar_noticia(title: str, desc: str) -> str:
    try:
        from src.shared.adapters.categorizacion import etiquetar_tematica

        return etiquetar_tematica(title, desc)
    except Exception:
        return "Noticias"


__all__ = [
    "deduplicate_by_similarity",
    "apply_diversity_penalty",
    "extract_frozen_terms",
    "apply_frozen_terms_penalty",
    "compute_score",
    "categorizar_noticia",
    "check_breaking_keywords",
    "is_valid_score",
    "sort_verified_news",
    "parse_iso_date",
    "resumir_noticia",
]
