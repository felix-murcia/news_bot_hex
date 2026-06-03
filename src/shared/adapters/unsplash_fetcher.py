import re
import requests
from dotenv import load_dotenv

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot")

load_dotenv(override=True)

UNSPLASH_ACCESS_KEY = Settings.UNSPLASH_ACCESS_KEY
if not UNSPLASH_ACCESS_KEY:
    logger.warning("[UNSPLASH] Missing UNSPLASH_ACCESS_KEY in .env")

UNSPLASH_API = Settings.UNSPLASH_API_URL


def filter_by_relevance(
    images: list[dict], query_keywords: list[str], min_score: float = 0.25
) -> list[dict]:
    """
    Filtra imágenes comparando su descripción (inglés) contra las keywords
    de búsqueda (inglés). Evita el problema de cross-language español/inglés.
    """
    if not images or not query_keywords:
        return images

    keyword_words = {w.lower() for kw in query_keywords for w in re.findall(r"\b[a-z]{3,}\b", kw.lower())}

    scored = []
    filtered = 0

    for img in images:
        description = (img.get("description") or img.get("alt") or "").lower()
        if not description:
            img["_relevance_score"] = 0.0
            filtered += 1
            continue

        desc_words = set(re.findall(r"\b[a-z]{3,}\b", description))
        common = desc_words.intersection(keyword_words)
        union = desc_words.union(keyword_words)
        score = len(common) / len(union) if union else 0.0
        img["_relevance_score"] = score

        if score >= min_score:
            scored.append(img)
        else:
            filtered += 1
            logger.debug(f"[RELEVANCE] Filtered (score={score:.2f}): {description[:60]}")

    scored.sort(key=lambda x: x["_relevance_score"], reverse=True)

    if filtered > 0:
        logger.info(f"[RELEVANCE] {filtered} images filtered, {len(scored)} passed")

    return scored


def get_used_ids() -> set:
    try:
        from src.shared.adapters.mongo_db import get_database
        db = get_database()
        return set(doc.get("id") for doc in db["used_unsplash_ids"].find({}, {"id": 1}))
    except Exception:
        return set()


def add_used_id(img_id: str):
    try:
        from src.shared.adapters.mongo_db import get_database
        db = get_database()
        db["used_unsplash_ids"].update_one({"id": img_id}, {"$set": {"id": img_id}}, upsert=True)
    except Exception:
        pass


class UnsplashFetcher:
    def __init__(self, mode: str = "news"):
        self.mode = mode

    def _search_images(self, query: str, limit: int = 10) -> list[dict]:
        if not UNSPLASH_ACCESS_KEY:
            return []
        used_ids = get_used_ids()
        try:
            headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
            params = {"query": query, "per_page": limit, "orientation": "landscape"}
            resp = requests.get(UNSPLASH_API, headers=headers, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"[UNSPLASH] API error: {resp.status_code}")
                return []
            images = []
            for img in resp.json().get("results", []):
                img_id = img.get("id")
                if img_id and img_id not in used_ids:
                    urls = img.get("urls", {})
                    images.append({
                        "id": img_id,
                        "url": urls.get("raw"),
                        "full_url": urls.get("full"),
                        "regular_url": urls.get("regular"),
                        "small_url": urls.get("small"),
                        "description": img.get("description") or img.get("alt_description", ""),
                        "user": img.get("user", {}).get("name", ""),
                    })
            return images
        except Exception as e:
            logger.warning(f"[UNSPLASH] Search error: {e}")
            return []

    def fetch_for_posts(self, posts: list) -> list:
        from src.shared.adapters.image_query_generator import generar_keywords_visuales_con_llm

        changed = 0
        fallback_url = Settings.WP_DEFAULT_IMAGE_URL

        for post in posts:
            if post.get("unsplash_image"):
                continue

            current_image = post.get("image_url", "")
            if current_image and current_image != fallback_url:
                continue

            title = post.get("title", "") or post.get("tweet", "")
            if not title:
                continue

            content = post.get("content") or post.get("article") or ""
            category = post.get("tema") or post.get("theme") or post.get("category") or ""

            keywords = generar_keywords_visuales_con_llm(title, content)
            if not keywords:
                logger.warning(f"[UNSPLASH] No keywords for '{title[:40]}'")
                continue

            query = " ".join(keywords[:4])
            raw_images = self._search_images(query, limit=10)
            relevant = filter_by_relevance(raw_images, keywords)

            if not relevant:
                logger.warning(f"[UNSPLASH] No relevant images for '{title[:40]}' (query: {query})")
                continue

            selected = relevant[0]
            img_id = selected.get("id")
            regular_url = selected.get("regular_url") or selected.get("url") or ""
            full_url = selected.get("full_url") or regular_url

            post["unsplash_image"] = regular_url
            post["unsplash_image_url"] = full_url
            post["unsplash_id"] = img_id
            post["image_credit"] = selected.get("user") or "Unsplash"
            post["alt_text"] = (selected.get("description") or title)[:200]
            post["image_url"] = regular_url

            if img_id:
                add_used_id(img_id)

            changed += 1
            score = selected.get("_relevance_score", 0.0)
            logger.info(f"[UNSPLASH] ✅ {title[:40]}: {regular_url[:40]} (score={score:.2f})")

        logger.info(f"[UNSPLASH] {changed} images assigned")
        return posts

    def fetch_from_mongo(self) -> int:
        try:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
            coll = db["generated_posts"]
            posts = list(coll.find({}))
            if not posts:
                logger.warning("[UNSPLASH] No posts to enrich")
                return 0
            self.fetch_for_posts(posts)
            for post in posts:
                post_id = post.pop("_id", None)
                if post_id:
                    coll.update_one({"_id": post_id}, {"$set": post})
            return len(posts)
        except Exception as e:
            logger.error(f"[UNSPLASH] Error: {e}")
            return 0


def run(mode: str = "news") -> int:
    logger.info(f"[UNSPLASH] Running (mode: {mode})")
    return UnsplashFetcher(mode=mode).fetch_from_mongo()


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "news")
