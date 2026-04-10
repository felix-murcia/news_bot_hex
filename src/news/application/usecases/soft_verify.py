from datetime import datetime
from typing import List, Dict, Set, Optional
from src.news.domain.entities.verified_article import VerifiedArticle
from src.news.domain.ports import (
    VerifiedNewsRepository,
    PublishedUrlsRepository,
    ContentExtractor,
)
from src.news.infrastructure.adapters import (
    MongoVerifiedNewsRepository,
    MongoPublishedUrlsRepository,
    JinaContentExtractor,
)
from src.shared.adapters.cache_manager import (
    load_content_from_cache,
    save_content_to_cache,
    clear_old_cache,
)

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")

LIMITS = {"ttl_days": 7, "max_urls": 300}
MIN_CHARS = 800
MIN_SCORE = 12
MAX_CANDIDATES_TO_PROCESS = 20


def load_verified_all() -> List[Dict]:
    from src.shared.adapters.mongo_db import get_database

    try:
        db = get_database()
        coll = db["verified_all"]
        news = list(coll.find({}))
        for n in news:
            n.pop("_id", None)
        logger.info(f"[SOFT] Cargadas {len(news)} noticias verificadas desde MongoDB")
        return news
    except Exception as e:
        logger.error(f"[SOFT] Error cargando verified_all: {e}")
        return []


def load_published_from_mongo(ttl_days: int, max_urls: int) -> Set[str]:
    repo = MongoPublishedUrlsRepository()
    return repo.get_urls(ttl_days, max_urls)


def save_published_to_mongo(urls: Set[str], ttl_days: int, max_urls: int):
    repo = MongoPublishedUrlsRepository()
    repo.save_urls(urls, ttl_days, max_urls)


def clear_verified_news():
    repo = MongoVerifiedNewsRepository()
    repo.delete_all_news()
    logger.info("[SOFT] verified_news vaciada en MongoDB")


def save_verified_news(news_item: Dict) -> bool:
    try:
        if "title" not in news_item or not news_item["title"]:
            news_item["title"] = "Noticia sin título"

        news_item["selected_at"] = datetime.now().isoformat()
        news_item["selection_strategy"] = news_item.get("selection_strategy", "unknown")

        repo = MongoVerifiedNewsRepository()
        repo.delete_all_news()
        article = VerifiedArticle.from_dict(news_item)
        repo.insert_news([article])
        logger.info(f"[SOFT] Noticia guardada en MongoDB (verified_news)")
        return True

    except Exception as e:
        logger.error(f"[SOFT] Error guardando verified_news: {e}")
        return False


def add_to_published_urls(url: str) -> bool:
    repo = MongoPublishedUrlsRepository()
    urls = repo.get_urls(LIMITS["ttl_days"], LIMITS["max_urls"])
    urls.add(url)
    return repo.save_urls(urls, LIMITS["ttl_days"], LIMITS["max_urls"])


def sort_by_score_then_date(news_list: List[Dict]) -> List[Dict]:
    def sort_key(item):
        return (
            int(item.get("score", 0)),
            parse_iso_date(item.get("publishedAt") or ""),
        )

    return sorted(news_list, key=sort_key, reverse=True)


def sort_by_date_then_score(news_list: List[Dict]) -> List[Dict]:
    def sort_key(item):
        return (
            parse_iso_date(item.get("publishedAt") or ""),
            int(item.get("score", 0)),
        )

    return sorted(news_list, key=sort_key, reverse=True)


def parse_iso_date(date_str: str) -> datetime:
    if not date_str:
        return datetime.min
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.min


class SoftVerifyUseCase:
    """Caso de uso para verificación soft - selecciona noticia para publicar."""

    def __init__(
        self,
        verified_repo: VerifiedNewsRepository = None,
        published_urls_repo: PublishedUrlsRepository = None,
        content_extractor: ContentExtractor = None,
    ):
        self._verified_repo = verified_repo or MongoVerifiedNewsRepository()
        self._published_urls_repo = (
            published_urls_repo or MongoPublishedUrlsRepository()
        )
        self._content_extractor = content_extractor or JinaContentExtractor()

    def execute(self) -> dict:
        logger.info("[SOFT] ===== INICIANDO VERIFICADOR SOFT =====")

        clear_old_cache(max_age_hours=72)

        all_news = load_verified_all()
        if not all_news:
            logger.warning("[SOFT] No hay noticias verificadas para procesar.")
            clear_verified_news()
            return {"status": "error", "message": "No hay noticias verificadas"}

        published_urls = load_published_from_mongo(
            LIMITS["ttl_days"], LIMITS["max_urls"]
        )

        unpublished_news = [
            n for n in all_news if n.get("url") and n.get("url") not in published_urls
        ]
        logger.info(
            f"[SOFT] {len(unpublished_news)}/{len(all_news)} noticias no publicadas"
        )

        if len(unpublished_news) == 0:
            logger.warning("[SOFT] Todas las noticias ya han sido publicadas")
            clear_verified_news()
            return {"status": "error", "message": "Todas las noticias ya publicadas"}

        high_score_news = [
            n for n in unpublished_news if int(n.get("score", 0)) >= MIN_SCORE
        ]
        logger.info(f"[SOFT] {len(high_score_news)} noticias con score ≥{MIN_SCORE}")

        selected_news = None

        logger.info("[SOFT] ===== ITERACIÓN 1: CRITERIO ESTRICTO =====")
        candidates_iter1 = sort_by_score_then_date(unpublished_news)

        for idx, candidate in enumerate(candidates_iter1[:MAX_CANDIDATES_TO_PROCESS]):
            url = candidate.get("url", "")
            score = int(candidate.get("score", 0))
            logger.info(f"[SOFT] Iter1 #{idx + 1}: Score={score}, URL={url[:60]}...")

            content, method = self._content_extractor.extract(url)
            content_length = len(content) if content else 0

            if content_length >= MIN_CHARS or score >= 15:
                candidate["extracted_content"] = content or ""
                candidate["extracted_content_length"] = content_length
                candidate["extraction_method"] = method
                candidate["selection_reason"] = (
                    f"Iter1: {content_length} chars >= {MIN_CHARS}"
                )
                candidate["selection_strategy"] = "strict"
                selected_news = candidate
                logger.info(
                    f"[SOFT] ✅ SELECCIONADA: {selected_news['selection_reason']}"
                )
                break
            else:
                logger.info(
                    f"[SOFT] ❌ Rechazada: solo {content_length} chars < {MIN_CHARS}"
                )

        if not selected_news:
            logger.info("[SOFT] ===== ITERACIÓN 2: CRITERIO RELAJADO =====")
            candidates_iter2 = sort_by_date_then_score(unpublished_news)

            for idx, candidate in enumerate(
                candidates_iter2[:MAX_CANDIDATES_TO_PROCESS]
            ):
                url = candidate.get("url", "")
                score = int(candidate.get("score", 0))
                logger.info(
                    f"[SOFT] Iter2 #{idx + 1}: Score={score}, URL={url[:60]}..."
                )

                content, method = self._content_extractor.extract(url)
                content_length = len(content) if content else 0

                if content_length >= MIN_CHARS:
                    candidate["extracted_content"] = content or ""
                    candidate["extracted_content_length"] = content_length
                    candidate["extraction_method"] = method
                    candidate["selection_reason"] = (
                        f"Iter2: {content_length} chars >= {MIN_CHARS}"
                    )
                    candidate["selection_strategy"] = "relaxed"
                    selected_news = candidate
                    logger.info(
                        f"[SOFT] ✅ SELECCIONADA: {selected_news['selection_reason']}"
                    )
                    break
                else:
                    logger.info(
                        f"[SOFT] ❌ Rechazada: solo {content_length} chars < {MIN_CHARS}"
                    )

        if not selected_news:
            logger.warning("[SOFT] Ninguna noticia alcanzó el mínimo de caracteres")
            clear_verified_news()
            return {"status": "error", "message": "Ninguna noticia alcanzó el mínimo"}

        return self._process_selected(selected_news, published_urls)

    def _process_selected(self, selected_news: Dict, published_urls: Set[str]) -> dict:
        url = selected_news["url"]

        cached_content, _ = load_content_from_cache(url)
        if cached_content:
            selected_news["extracted_content"] = cached_content
            selected_news["extracted_content_length"] = len(cached_content)

        if not save_verified_news(selected_news):
            logger.error("[SOFT] Error guardando verified_news")
            return {"status": "error", "message": "Error guardando"}

        if not add_to_published_urls(url):
            logger.error("[SOFT] Error actualizando published_urls")

        published_urls.add(url)
        save_published_to_mongo(published_urls, LIMITS["ttl_days"], LIMITS["max_urls"])

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


def main():
    use_case = SoftVerifyUseCase()
    return use_case.execute()


def clear_verified_news_wrapper():
    clear_verified_news()
