from datetime import datetime
from typing import List, Dict, Set

from src.news.domain.entities.verified_article import VerifiedArticle
from src.news.domain.ports import (
    VerifiedNewsRepository,
    PublishedUrlsRepository,
    ContentExtractor,
)
from src.shared.adapters.cache_manager import (
    load_content_from_cache,
    clear_old_cache,
)

from config.logging_config import get_logger

logger = get_logger("news_bot.usecase.soft_verify")

LIMITS = {"ttl_days": 7, "max_urls": 300}
MIN_CHARS = 800
MIN_SCORE = 12
MAX_CANDIDATES_TO_PROCESS = 20


def _load_verified_all(repo) -> List[Dict]:
    """Load all verified articles from the verified_all collection via repo."""
    try:
        news = repo.get_all_for_soft_verify()
        logger.info(f"[SOFT] Cargadas {len(news)} noticias desde repositorio")
        return news
    except Exception as e:
        logger.error(f"[SOFT] Error cargando noticias: {e}")
        return []


def _save_verified_news(repo, news_item: Dict) -> bool:
    """Save selected news via repository."""
    try:
        if "title" not in news_item or not news_item["title"]:
            news_item["title"] = "Noticia sin título"
        news_item["selected_at"] = datetime.now().isoformat()
        news_item["selection_strategy"] = news_item.get("selection_strategy", "unknown")

        repo.delete_all_news()
        article = VerifiedArticle.from_dict(news_item)
        repo.insert_news([article])
        logger.info("[SOFT] Noticia guardada en repositorio")
        return True
    except Exception as e:
        logger.error(f"[SOFT] Error guardando: {e}")
        return False


def _add_to_published_urls(repo, url: str) -> bool:
    """Add URL to published via repository."""
    urls = repo.get_urls(LIMITS["ttl_days"], LIMITS["max_urls"])
    urls.add(url)
    return repo.save_urls(urls, LIMITS["ttl_days"], LIMITS["max_urls"])


def _load_published_urls(repo) -> Set[str]:
    """Load published URLs via repository."""
    return repo.get_urls(LIMITS["ttl_days"], LIMITS["max_urls"])


class SoftVerifyUseCase:
    """Caso de uso para verificación soft - selecciona noticia para publicar.

    All dependencies are injected via constructor — no infrastructure imports.
    """

    def __init__(
        self,
        verified_repo: VerifiedNewsRepository,
        published_urls_repo: PublishedUrlsRepository,
        content_extractor: ContentExtractor,
    ):
        self._verified_repo = verified_repo
        self._published_urls_repo = published_urls_repo
        self._content_extractor = content_extractor

    def execute(self) -> dict:
        logger.info("[SOFT] ===== INICIANDO VERIFICADOR SOFT =====")

        clear_old_cache(max_age_hours=72)

        all_news = _load_verified_all(self._verified_repo)
        if not all_news:
            logger.warning("[SOFT] No hay noticias verificadas para procesar.")
            self._verified_repo.delete_all_news()
            return {"status": "error", "message": "No hay noticias verificadas"}

        published_urls = _load_published_urls(self._published_urls_repo)

        unpublished_news = [
            n for n in all_news if n.get("url") and n.get("url") not in published_urls
        ]
        logger.info(
            f"[SOFT] {len(unpublished_news)}/{len(all_news)} noticias no publicadas"
        )

        if len(unpublished_news) == 0:
            logger.warning("[SOFT] Todas las noticias ya han sido publicadas")
            self._verified_repo.delete_all_news()
            return {"status": "error", "message": "Todas las noticias ya publicadas"}

        selected_news = self._select_news(unpublished_news)
        if not selected_news:
            logger.warning("[SOFT] Ninguna noticia alcanzó el mínimo de caracteres")
            self._verified_repo.delete_all_news()
            return {"status": "error", "message": "Ninguna noticia alcanzó el mínimo"}

        return self._process_selected(selected_news, published_urls)

    def _select_news(self, unpublished_news: List[Dict]) -> Dict | None:
        """Select the best news article through two iteration passes."""
        selected_news = None

        # Iteration 1: strict criteria
        logger.info("[SOFT] ===== ITERACIÓN 1: CRITERIO ESTRICTO =====")
        candidates_iter1 = sorted(
            unpublished_news,
            key=lambda x: (int(x.get("score", 0)), _parse_iso_date(x.get("publishedAt") or "")),
            reverse=True,
        )

        for idx, candidate in enumerate(candidates_iter1[:MAX_CANDIDATES_TO_PROCESS]):
            if self._try_candidate(candidate, "strict", idx + 1, "Iter1"):
                selected_news = candidate
                break

        if selected_news:
            return selected_news

        # Iteration 2: relaxed criteria
        logger.info("[SOFT] ===== ITERACIÓN 2: CRITERIO RELAJADO =====")
        candidates_iter2 = sorted(
            unpublished_news,
            key=lambda x: (_parse_iso_date(x.get("publishedAt") or ""), int(x.get("score", 0))),
            reverse=True,
        )

        for idx, candidate in enumerate(candidates_iter2[:MAX_CANDIDATES_TO_PROCESS]):
            if self._try_candidate(candidate, "relaxed", idx + 1, "Iter2"):
                selected_news = candidate
                break

        return selected_news

    def _try_candidate(self, candidate: Dict, strategy: str, idx: int, prefix: str) -> bool:
        """Try to select a candidate article. Returns True if selected."""
        url = candidate.get("url", "")
        score = int(candidate.get("score", 0))
        logger.info(f"[SOFT] {prefix} #{idx}: Score={score}, URL={url[:60]}...")

        content, method = self._content_extractor.extract(url)
        content_length = len(content) if content else 0

        min_chars = MIN_CHARS if strategy == "relaxed" else MIN_CHARS
        passes = content_length >= min_chars or (strategy == "strict" and score >= 15)

        if passes:
            candidate["extracted_content"] = content or ""
            candidate["extracted_content_length"] = content_length
            candidate["extraction_method"] = method
            candidate["selection_reason"] = f"{prefix}: {content_length} chars >= {min_chars}"
            candidate["selection_strategy"] = strategy
            logger.info(f"[SOFT] ✅ SELECCIONADA: {candidate['selection_reason']}")
            return True
        else:
            logger.info(f"[SOFT] ❌ Rechazada: solo {content_length} chars < {min_chars}")
            return False

    def _process_selected(self, selected_news: Dict, published_urls: Set[str]) -> dict:
        url = selected_news["url"]

        cached_content, _ = load_content_from_cache(url)
        if cached_content:
            selected_news["extracted_content"] = cached_content
            selected_news["extracted_content_length"] = len(cached_content)

        if not _save_verified_news(self._verified_repo, selected_news):
            logger.error("[SOFT] Error guardando verified_news")
            return {"status": "error", "message": "Error guardando"}

        if not _add_to_published_urls(self._published_urls_repo, url):
            logger.error("[SOFT] Error actualizando published_urls")

        published_urls.add(url)
        self._published_urls_repo.save_urls(
            published_urls, LIMITS["ttl_days"], LIMITS["max_urls"]
        )

        logger.info("[SOFT] ===== PROCESO COMPLETADO =====")
        logger.info(f"[SOFT] Estrategia: {selected_news.get('selection_strategy')}")
        logger.info(f"[SOFT] Razón: {selected_news.get('selection_reason')}")
        logger.info(f"[SOFT] Score: {selected_news.get('score', 0)}")
        logger.info(
            f"[SOFT] Caracteres: {selected_news.get('extracted_content_length', 0)}"
        )

        return {
            "status": "success",
            "title": selected_news.get("title", ""),
            "url": url,
            "score": selected_news.get("score", 0),
            "strategy": selected_news.get("selection_strategy"),
        }


def _parse_iso_date(date_str: str) -> datetime:
    if not date_str:
        return datetime.min
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.min


def main():
    from src.news.infrastructure.adapters import (
        MongoVerifiedNewsRepository,
        MongoPublishedUrlsRepository,
        JinaContentExtractor,
    )

    use_case = SoftVerifyUseCase(
        verified_repo=MongoVerifiedNewsRepository(),
        published_urls_repo=MongoPublishedUrlsRepository(),
        content_extractor=JinaContentExtractor(),
    )
    return use_case.execute()


def clear_verified_news_wrapper():
    from src.news.infrastructure.adapters import MongoVerifiedNewsRepository
    repo = MongoVerifiedNewsRepository()
    repo.delete_all_news()
    logger.info("[SOFT] verified_news vaciado en MongoDB")
