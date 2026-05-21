"""Cleanup usecase - reset pipeline state at the beginning."""

from config.logging_config import get_logger
from src.news.domain.ports import (
    VerifiedNewsRepository,
    GeneratedPostsRepository,
    GeneratedArticlesRepository,
)

logger = get_logger("news_bot.usecase.cleanup")


class CleanupPipelineUseCase:
    """Clean up collections before pipeline execution (like the legacy wrapper did)."""

    def __init__(
        self,
        verified_repo: VerifiedNewsRepository,
        generated_posts_repo: GeneratedPostsRepository,
        generated_articles_repo: GeneratedArticlesRepository,
    ):
        self._verified_repo = verified_repo
        self._generated_posts_repo = generated_posts_repo
        self._generated_articles_repo = generated_articles_repo

    def execute(self) -> dict:
        """Clean verified_news, generated_posts, and generated_articles collections."""
        logger.info("[CLEANUP] Iniciando limpieza de estado")

        try:
            self._verified_repo.delete_all_news()
            logger.info("[CLEANUP] ✅ Limpiada colección verified_news")
        except Exception as e:
            logger.warning(f"[CLEANUP] ⚠️ Error limpiando verified_news: {e}")

        try:
            self._generated_posts_repo.delete_all()
            logger.info("[CLEANUP] ✅ Limpiada colección generated_posts")
        except Exception as e:
            logger.warning(f"[CLEANUP] ⚠️ Error limpiando generated_posts: {e}")

        try:
            self._generated_articles_repo.delete_all()
            logger.info("[CLEANUP] ✅ Limpiada colección generated_articles")
        except Exception as e:
            logger.warning(f"[CLEANUP] ⚠️ Error limpiando generated_articles: {e}")

        logger.info("[CLEANUP] Limpieza completada")
        return {"status": "ok", "message": "Cleanup completed"}


def main():
    from src.news.infrastructure.adapters import (
        MongoVerifiedNewsRepository,
        MongoGeneratedPostsRepository,
        MongoGeneratedArticlesRepository,
    )

    usecase = CleanupPipelineUseCase(
        verified_repo=MongoVerifiedNewsRepository(),
        generated_posts_repo=MongoGeneratedPostsRepository(),
        generated_articles_repo=MongoGeneratedArticlesRepository(),
    )
    return usecase.execute()


if __name__ == "__main__":
    main()
