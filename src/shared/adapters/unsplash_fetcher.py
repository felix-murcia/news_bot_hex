import os
import logging
import requests
import random
import re
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")

load_dotenv()
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
if not UNSPLASH_ACCESS_KEY:
    logger.warning("[UNSPLASH] Falta UNSPLASH_ACCESS_KEY en .env")

UNSPLASH_API = "https://api.unsplash.com/search/photos"

UNSPLASH_SYNONYMS = {
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


def clean_title(title: str) -> str:
    title = re.sub(r"\b(LIVE|BREAKING|UPDATE)\b[:\-–]*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"[^\w\s]", "", title)
    return title.strip()


def fallback_unsplash_query(query: str) -> str:
    keyword = query.lower().split()[0]
    fallback_terms = UNSPLASH_SYNONYMS.get(keyword, [])
    location_match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", query)
    location = location_match.group(1) if location_match else ""
    if fallback_terms:
        alt_term = random.choice(fallback_terms)
        return f"{alt_term} {location}".strip()
    elif location:
        return location
    else:
        return "noticia"


def search_unsplash(query: str, used_ids: set) -> dict | None:
    if not UNSPLASH_ACCESS_KEY:
        return None

    def fetch(q):
        try:
            headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
            params = {"query": q, "per_page": 30, "orientation": "landscape"}
            resp = requests.get(
                UNSPLASH_API, headers=headers, params=params, timeout=15
            )
            if resp.status_code != 200:
                logger.warning(f"[UNSPLASH] API error: {resp.status_code}")
                return None
            data = resp.json().get("results", [])
            for img in data:
                img_id = img.get("id")
                if img_id and img_id not in used_ids:
                    urls = img.get("urls", {})
                    return {
                        "id": img_id,
                        "url": urls.get("raw"),
                        "full_url": urls.get("full"),
                        "regular_url": urls.get("regular"),
                        "small_url": urls.get("small"),
                        "thumb_url": urls.get("thumb"),
                        "description": img.get("description")
                        or img.get("alt_description", ""),
                        "user": img.get("user", {}).get("name", ""),
                    }
            return None
        except Exception as e:
            logger.warning(f"[UNSPLASH] Error: {e}")
            return None

    result = fetch(query)
    if result:
        return result
    alt_query = fallback_unsplash_query(query)
    return fetch(alt_query)


def get_used_ids() -> set:
    try:
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        coll = db["used_unsplash_ids"]
        return set(doc.get("id") for doc in coll.find({}, {"id": 1}))
    except:
        return set()


def add_used_id(img_id: str):
    try:
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        coll = db["used_unsplash_ids"]
        coll.update_one({"id": img_id}, {"$set": {"id": img_id}}, upsert=True)
    except:
        pass


class UnsplashFetcher:
    def __init__(self, mode: str = "news"):
        self.mode = mode

    def fetch_for_posts(self, posts: list) -> list:
        changed = 0
        used_ids = get_used_ids()
        fallback_url = "https://api.nbes.blog/image-310/"

        for post in posts:
            if post.get("unsplash_image"):
                continue

            current_image = post.get("image_url", "")
            if current_image and current_image != fallback_url:
                continue

            title = post.get("title", "") or post.get("tweet", "")
            if not title:
                continue

            query = clean_title(title)[:100]
            result = search_unsplash(query, used_ids)

            if result:
                post["unsplash_image"] = result.get("regular_url")
                post["unsplash_image_url"] = result.get("full_url")
                post["unsplash_id"] = result.get("id")
                post["image_credit"] = result.get("user", "Unsplash")
                post["alt_text"] = result.get("description", title)[:200]
                post["image_url"] = result.get("regular_url")
                add_used_id(result.get("id"))
                changed += 1
                logger.info(
                    f"[UNSPLASH] ✅ {title[:40]}: {result.get('regular_url')[:40]}"
                )
            else:
                logger.warning(f"[UNSPLASH] No encontradas: {title[:40]}")

        logger.info(f"[UNSPLASH] ✅ {changed} imágenes encontradas")
        return posts

    def fetch_from_mongo(self) -> int:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_posts"]
            posts = list(coll.find({}))

            if not posts:
                logger.warning("[UNSPLASH] No hay posts para enriquecer")
                return 0

            self.fetch_for_posts(posts)

            for post in posts:
                post_id = post.get("_id")
                if post_id:
                    post.pop("_id", None)
                    coll.update_one({"_id": post_id}, {"$set": post})

            return len(posts)

        except Exception as e:
            logger.error(f"[UNSPLASH] Error: {e}")
            return 0


def run(mode: str = "news") -> int:
    logger.info(f"[UNSPLASH] Ejecutando (modo: {mode})")
    fetcher = UnsplashFetcher(mode=mode)
    return fetcher.fetch_from_mongo()


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "news"
    run(mode)
