"""Use case para transformar artículos raw (raw_news) a formato generated_articles.

Este paso conecta el flujo RSS_FETCH → FULL_VERIFICATION moviendo datos
desde la colección raw_news (ArticleRepository) a generated_articles
(GeneratedArticlesRepository), que es lo que FullVerifyNewsUseCase lee.
"""

from typing import List, Dict
from src.news.domain.ports import ArticleRepository, GeneratedArticlesRepository
from src.news.domain.entities.article import Article

import logging

logger = logging.getLogger(__name__)


class PrepareArticlesUseCase:
    """Transforma artículos crudos de raw_news al formato expected por generated_articles."""

    def __init__(
        self,
        raw_articles_repo: ArticleRepository,
        generated_articles_repo: GeneratedArticlesRepository,
    ):
        self._raw_repo = raw_articles_repo
        self._generated_repo = generated_articles_repo

    def execute(self) -> dict:
        """Ejecuta la transformación y guardado.

        Returns:
            dict con status, processed count, y error si falla.
        """
        try:
            raw_articles = self._raw_repo.get_all_articles()
            if not raw_articles:
                logger.warning("[PREPARE] No hay artículos en raw_news para procesar")
                return {"status": "error", "message": "No hay artículos en raw_news para procesar", "processed": 0}

            # Convertir Article objects a dicts para generated_articles
            generated_articles = [article.to_dict() for article in raw_articles]

            # Guardar en generated_articles (sobrescribe la colección completa)
            success = self._generated_repo.save_all(generated_articles)
            if not success:
                return {"status": "error", "message": "Error guardando en generated_articles", "processed": 0}

            logger.info(f"[PREPARE] {len(generated_articles)} artículos preparados para verificación")
            return {"status": "success", "processed": len(generated_articles)}

        except Exception as e:
            logger.error(f"[PREPARE] Error transformando artículos: {e}")
            return {"status": "error", "message": str(e), "processed": 0}