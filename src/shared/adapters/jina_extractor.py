import requests
import re
import time
from typing import Tuple, Optional
from config.logging_config import get_logger
from config.settings import Settings

logger = get_logger("news_bot")

# Jina antepone su propia cabecera al cuerpo y la separa en campos propios
# (Title, URL Source, Published Time, Warning) que ademas separa con lineas en
# blanco. Sin limpiarla, esos prefijos ("Title:", "Published Time:", ...) acaba
# en el titulo del articulo, en el slug, en las keywords SEO y en el texto que
# ve el modelo de IA.
_JINA_MARKDOWN_MARKER = re.compile(r"(?m)^\s*Markdown Content:\s*$")
_JINA_HEADER_LINE = re.compile(r"\s*(Title|Published Time|URL Source|Warning|Markdown Content):")


_JINA_TITLE_LINE = re.compile(r"(?m)^Title:\s*(.+?)\s*$")
_H1_LINE = re.compile(r"^\s*#\s+\S")


def extraer_titulo_jina(raw: Optional[str]) -> str:
    """Devuelve el campo 'Title:' de la respuesta de Jina, o '' si no existe.

    Solo se busca en la zona ANTES del marcador 'Markdown Content:' para no
    confundirse con lineas 'Title:' que aparezcan dentro del propio artículo.
    """
    if not raw:
        return ""
    marker = _JINA_MARKDOWN_MARKER.search(raw)
    zona = raw[: marker.start()] if marker else raw
    match = _JINA_TITLE_LINE.search(zona)
    return match.group(1).strip() if match else ""


def quitar_ruido_inicial(cuerpo: str, max_lineas_busqueda: int = 150) -> str:
    """Recorta el ruido de página que Jina antepone al artículo.

    En páginas con banner de cookies (euronews, elpais, ...) el cuerpo va:
    [banner + navegación] → [H1 del artículo] → [cuerpo]. Si el primer H1
    markdown aparece dentro de las primeras `max_lineas_busqueda` líneas, el
    cuerpo empieza ahí; si no hay ningún H1 cerca, no se toca nada.
    """
    if not cuerpo:
        return cuerpo
    lineas = cuerpo.split("\n")
    for i, linea in enumerate(lineas[:max_lineas_busqueda]):
        if _H1_LINE.match(linea):
            return "\n".join(lineas[i:]).lstrip()
    return cuerpo


def limpiar_cabecera_jina(contenido: str) -> str:
    """Elimina la cabecera de Jina del principio del contenido.

    Devuelve el cuerpo limpio. Jina separa sus campos de metadata con lineas en
    blanco, asi que no basta con quitar el primer bloque: si hay el marcador
    "Markdown Content:", el cuerpo es todo lo que va despues; en caso contrario
    se quitan las lineas de cabecera iniciales tolerando lineas en blanco entre
    ellas. Si no hay cabecera reconocible, devuelve la entrada sin tocar.
    """
    if not contenido:
        return contenido

    marker = _JINA_MARKDOWN_MARKER.search(contenido)
    if marker:
        return contenido[marker.end():].lstrip()

    lineas = contenido.split("\n")
    i = 0
    while i < len(lineas):
        if lineas[i].strip() == "":
            i += 1
            continue
        if _JINA_HEADER_LINE.match(lineas[i]):
            i += 1
            continue
        break
    return "\n".join(lineas[i:]).lstrip()

class JinaExtractor:
    def __init__(self):
        self.stats = {"success": 0, "failures": 0, "requests": 0, "last_request": None}
        logger.info("[JINA] Extractor inicializado")

    def extract(self, url: str, max_retries: int = 2) -> Tuple[Optional[str], str, str]:
        """Devuelve (contenido, metodo, titulo).

        `titulo` es el campo 'Title:' de la cabecera de Jina (vacio si no
        viene) y `contenido` va recortado de cualquier banner de cookies o
        navegación que Jina anteponga al H1 del artículo.
        """
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
                    titulo = extraer_titulo_jina(response.text)
                    content = quitar_ruido_inicial(limpiar_cabecera_jina(response.text))
                    if len(content) > 200:
                        self.stats["success"] += 1
                        self.stats["last_request"] = time.time()
                        logger.info(f"[JINA] Exito ({len(content)} chars, título: {titulo[:60]!r})")
                        return content, "jina_success", titulo
                    logger.warning(f"[JINA] Contenido corto ({len(content)} chars)")
                else:
                    logger.warning(f"[JINA] HTTP {response.status_code}")

            except Exception as e:
                logger.warning(f"[JINA] Error: {type(e).__name__}: {str(e)[:100]}")
                time.sleep(2)

        self.stats["failures"] += 1
        logger.error(f"[JINA] Fallo total para {url[:60]}")
        return None, "jina_failed", ""


jina_extractor = JinaExtractor()


def extraer_contenido(url: str) -> Tuple[Optional[str], str, str]:
    return jina_extractor.extract(url)
