import logging
from typing import Tuple

from src.news.domain.ports import ContentExtractor

from config.logging_config import get_logger

logger = get_logger("news_bot.infra.news_adapters")


class JinaContentExtractor(ContentExtractor):
    def extract(self, url: str) -> Tuple[str, str]:
        try:
            from src.shared.adapters.jina_extractor import extraer_contenido

            contenido, metodo = extraer_contenido(url)
            return contenido, metodo
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return "", "error"
