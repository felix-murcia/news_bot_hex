import requests
import time
from typing import Tuple, Optional
from config.logging_config import get_logger

logger = get_logger("news_bot")


class JinaExtractor:
    def __init__(self):
        self.stats = {"success": 0, "failures": 0, "requests": 0, "last_request": None}
        logger.info("[JINA] Extractor inicializado")

    def extract(self, url: str, max_retries: int = 2) -> Tuple[Optional[str], str]:
        logger.info(f"[JINA] Extrayendo {url[:60]}...")
        self.stats["requests"] += 1
        proxy_url = f"https://r.jina.ai/{url}"

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"[JINA] Reintento {attempt + 1}/{max_retries}")

                response = requests.get(
                    proxy_url,
                    timeout=25,
                    headers={
                        "User-Agent": "NewsBot-Jina/1.0",
                        "Accept": "text/plain,text/markdown,*/*",
                        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                    },
                )

                if response.status_code == 200:
                    content = response.text
                    if len(content) > 200:
                        self.stats["success"] += 1
                        self.stats["last_request"] = time.time()
                        logger.info(f"[JINA] Exito ({len(content)} chars)")
                        return content, "jina_success"
                    logger.warning(f"[JINA] Contenido corto ({len(content)} chars)")
                else:
                    logger.warning(f"[JINA] HTTP {response.status_code}")

            except Exception as e:
                logger.warning(f"[JINA] Error: {type(e).__name__}: {str(e)[:100]}")
                time.sleep(2)

        self.stats["failures"] += 1
        logger.error(f"[JINA] Fallo total para {url[:60]}")
        return None, "jina_failed"


jina_extractor = JinaExtractor()


def extraer_contenido(url: str) -> Tuple[Optional[str], str]:
    return jina_extractor.extract(url)
