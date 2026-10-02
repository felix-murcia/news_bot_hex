import requests
import re
import time
from typing import Tuple, Optional
from config.logging_config import get_logger
from config.settings import Settings

logger = get_logger("news_bot")

# Jina antepone su propia cabecera al cuerpo: "Title: <titulo>\n\nURL Source: <url>\n\n".
# Sin limpiarla, el prefijo "Title:" acaba en el título del artículo, en el slug
# (title-video-...), en las keywords SEO y en el texto que ve el modelo de IA.
_JINA_HEADER = re.compile(r"\A\s*(Title|Published Time|URL Source|Warning|Markdown Content):.*?(?=\n\s*\n|\Z)", re.DOTALL)


def limpiar_cabecera_jina(contenido: str) -> str:
    """Elimina la cabecera de Jina del principio del contenido.

    Devuelve el cuerpo limpio. Si no hay cabecera reconocible, devuelve la
    entrada sin tocar: es preferible no normalizar antes que truncar contenido.
    """
    if not contenido:
        return contenido

    limpio = _JINA_HEADER.sub("", contenido, count=1).lstrip()

    # Jina puede no poner línea en blanco tras "Title:"; en ese caso quitamos
    # las líneas de cabecera sueltas que queden al principio.
    lineas = limpio.split("\n")
    while lineas and re.match(
        r"\s*(Title|Published Time|URL Source|Warning|Markdown Content):", lineas[0]
    ):
        lineas.pop(0)
    return "\n".join(lineas).lstrip()

class JinaExtractor:
    def __init__(self):
        self.stats = {"success": 0, "failures": 0, "requests": 0, "last_request": None}
        logger.info("[JINA] Extractor inicializado")

    def extract(self, url: str, max_retries: int = 2) -> Tuple[Optional[str], str]:
        logger.info(f"[JINA] Extrayendo {url[:60]}...")
        self.stats["requests"] += 1
        proxy_url = f"https://r.jina.ai/{url}"

        headers = {
            "User-Agent": "NewsBot-Jina/1.0",
            "Accept": "text/plain,text/markdown,*/*",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        }
        
        if getattr(Settings, "JINA_API_KEY", None):
            headers["Authorization"] = f"Bearer {Settings.JINA_API_KEY}"

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"[JINA] Reintento {attempt + 1}/{max_retries}")

                response = requests.get(
                    proxy_url,
                    timeout=25,
                    headers=headers,
                )

                if response.status_code == 200:
                    content = limpiar_cabecera_jina(response.text)
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
