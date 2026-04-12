import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Tuple
from config.logging_config import get_logger

from config.settings import Settings

logger = get_logger("news_bot")

CACHE_DIR = Settings.CACHE_DIR
CACHE_DIR.mkdir(exist_ok=True, parents=True)


def get_cache_path(url: str, cache_dir: Optional[Path] = None) -> Path:
    if cache_dir is None:
        cache_dir = CACHE_DIR
    cache_dir.mkdir(exist_ok=True, parents=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return cache_dir / f"{url_hash}.txt"


def save_content_to_cache(url: str, content: str, method: str = "scraperapi") -> bool:
    try:
        if not content or len(content) < 100:
            logger.warning(
                f"[CACHE] Contenido demasiado corto para guardar: {len(content)} chars"
            )
            return False

        cache_file = get_cache_path(url)

        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(content)

        meta_file = cache_file.with_suffix(".json")
        meta_data = {
            "url": url,
            "method": method,
            "timestamp": time.time(),
            "length": len(content),
            "cache_file": cache_file.name,
        }

        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"[CACHE] Guardado en caché: {len(content)} chars → {cache_file.name}"
        )
        return True

    except Exception as e:
        logger.error(f"[CACHE] Error guardando caché: {e}")
        return False


def load_content_from_cache(
    url: str, max_age_hours: int = 6
) -> Tuple[Optional[str], str]:
    try:
        cache_file = get_cache_path(url)

        if not cache_file.exists():
            return None, "no_cache"

        file_age_hours = (time.time() - cache_file.stat().st_mtime) / 3600

        if file_age_hours > max_age_hours:
            logger.info(f"[CACHE] Archivo expirado ({file_age_hours:.1f}h), ignorando")
            return None, "cache_expired"

        with open(cache_file, "r", encoding="utf-8") as f:
            content = f.read()

        if len(content) < 100:
            logger.warning(
                f"[CACHE] Contenido en caché demasiado corto: {len(content)} chars"
            )
            return None, "cache_too_short"

        logger.info(
            f"[CACHE] Cargado desde caché: {len(content)} chars ({file_age_hours:.1f}h)"
        )
        return content, "cache_hit"

    except Exception as e:
        logger.error(f"[CACHE] Error cargando caché: {e}")
        return None, "cache_error"


def clear_old_cache(max_age_hours: int = 72) -> int:
    try:
        if not CACHE_DIR.exists():
            return 0

        deleted = 0
        now = time.time()

        for file in CACHE_DIR.glob("*.txt"):
            file_age_hours = (now - file.stat().st_mtime) / 3600
            if file_age_hours > max_age_hours:
                file.unlink()
                json_file = file.with_suffix(".json")
                if json_file.exists():
                    json_file.unlink()
                deleted += 1

        if deleted > 0:
            logger.info(
                f"[CACHE] Limpiados {deleted} archivos de caché > {max_age_hours}h"
            )

        return deleted

    except Exception as e:
        logger.error(f"[CACHE] Error limpiando caché: {e}")
        return 0
