import os
import requests
import random
import re
from dotenv import load_dotenv

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot")

load_dotenv(override=True)

GOOGLE_API_KEY = Settings.GOOGLE_SEARCH_API_KEY
GOOGLE_CX = Settings.GOOGLE_SEARCH_ENGINE_ID

if not GOOGLE_API_KEY or not GOOGLE_CX:
    logger.warning(
        "[GOOGLE] Missing GOOGLE_SEARCH_API_KEY or GOOGLE_SEARCH_ENGINE_ID in .env"
    )

GOOGLE_API = Settings.GOOGLE_API_URL

GOOGLE_SYNONYMS = {
    "protesta": ["manifestación", "reclamo", "activismo"],
    "tecnología": ["innovación", "dispositivo", "futuro"],
    "guerra": ["conflicto", "militar", "soldado"],
    "economía": ["finanzas", "mercado", "dinero"],
    "clima": ["medio ambiente", "naturaleza", "tormenta"],
    "salud": ["hospital", "médico", "enfermedad"],
    "educación": ["escuela", "estudiante", "aula"],
    "política": ["gobierno", "elecciones", "parlamento"],
    "energía": ["electricidad", "solar", "infraestructura"],
    "crimen": ["policía", "justicia", "investigación"],
}


# ============================================================
# Nuevo sistema de generación de queries para imágenes
# (Importamos la lógica compartida de unsplash_fetcher)
# ============================================================

from src.shared.adapters.unsplash_fetcher import (
    clean_title,
    extraer_entidades_imagen,
    extraer_concepto_visual_principal,
    generar_query_imagen,
    enrich_image_query,
)


def fallback_google_query(query: str) -> str:
    keyword = query.lower().split()[0]
    fallback_terms = GOOGLE_SYNONYMS.get(keyword, [])
    location_match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", query)
    location = location_match.group(1) if location_match else ""
    if fallback_terms:
        alt_term = random.choice(fallback_terms)
        return f"{alt_term} {location}".strip()
    elif location:
        return location
    else:
        return "noticia"


def search_google_images(query: str, used_ids: set) -> dict | None:
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return None

    def fetch(q):
        try:
            params = {
                "key": GOOGLE_API_KEY,
                "cx": GOOGLE_CX,
                "q": q,
                "searchType": "image",
                "num": 10,
            }
            resp = requests.get(GOOGLE_API, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"[GOOGLE] API error: {resp.status_code}")
                return None
            data = resp.json().get("items", [])
            for img in data:
                link = img.get("link")
                img_id = link or str(hash(link))[:20]
                if link and link not in used_ids:
                    return {
                        "id": img_id,
                        "url": link,
                        "thumbnail": img.get("image", {}).get("thumbnailLink"),
                        "context": img.get("image", {}).get("contextLink"),
                    }
            return None
        except Exception as e:
            logger.warning(f"[GOOGLE] Error: {e}")
            return None

    result = fetch(query)
    if result:
        return result
    alt_query = fallback_google_query(query)
    return fetch(alt_query)


def get_used_ids() -> set:
    try:
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        coll = db["used_google_ids"]
        return set(doc.get("id") for doc in coll.find({}, {"id": 1}))
    except:
        return set()


def add_used_id(img_id: str):
    try:
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        coll = db["used_google_ids"]
        coll.update_one({"id": img_id}, {"$set": {"id": img_id}}, upsert=True)
    except:
        pass


class GoogleImagesFetcher:
    def __init__(self, mode: str = "news"):
        self.mode = mode

    def fetch_for_posts(self, posts: list) -> list:
        changed = 0
        used_ids = get_used_ids()
        fallback_url = Settings.WP_DEFAULT_IMAGE_URL

        for post in posts:
            if post.get("google_image"):
                continue

            current_image = post.get("image_url", "")
            if current_image and current_image != fallback_url:
                continue

            title = post.get("title", "") or post.get("tweet", "")
            if not title:
                continue

            # Get theme if available for better query enrichment
            theme = post.get("tema") or post.get("theme") or post.get("category")
            content = post.get("content") or post.get("article") or ""

            # Enrich query for better image results
            use_title_only = self.mode == "news"
            query = enrich_image_query(title, theme, content, use_title_only=use_title_only)
            result = search_google_images(query, used_ids)

            if result:
                img_url = result.get("url")
                img_id = result.get("id")
                post["google_image"] = img_url
                post["google_image_url"] = img_url
                # NO establecer image_url aquí — el ImageEnricher lo hará
                # después de validar que la imagen es realmente accesible
                post["image_credit"] = post.get("image_credit") or "Google Images"
                post["alt_text"] = post.get("alt_text") or title[:200]
                if img_id:
                    add_used_id(img_id)
                changed += 1
                logger.info(
                    f"[GOOGLE] ✅ {title[:40]}: {img_url[:40] if img_url else ''}"
                )
            else:
                logger.warning(f"[GOOGLE] No encontrada: {title[:40]}")

        logger.info(f"[GOOGLE] ✅ {changed} imágenes encontradas")
        return posts

    def fetch_from_mongo(self) -> int:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_posts"]
            posts = list(coll.find({}))

            if not posts:
                logger.warning("[GOOGLE] No hay posts para enriquecer")
                return 0

            self.fetch_for_posts(posts)

            for post in posts:
                post_id = post.get("_id")
                if post_id:
                    post.pop("_id", None)
                    coll.update_one({"_id": post_id}, {"$set": post})

            return len(posts)

        except Exception as e:
            logger.error(f"[GOOGLE] Error: {e}")
            return 0


def run(mode: str = "news") -> int:
    logger.info(f"[GOOGLE] Ejecutando (modo: {mode})")
    fetcher = GoogleImagesFetcher(mode=mode)
    return fetcher.fetch_from_mongo()


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "news"
    run(mode)
