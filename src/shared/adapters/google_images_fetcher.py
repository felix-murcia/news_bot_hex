import re
import requests
from dotenv import load_dotenv

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot")

load_dotenv(override=True)

GOOGLE_API_KEY = Settings.GOOGLE_SEARCH_API_KEY
GOOGLE_CX = Settings.GOOGLE_SEARCH_ENGINE_ID

if not GOOGLE_API_KEY or not GOOGLE_CX:
    logger.warning("[GOOGLE] Missing GOOGLE_SEARCH_API_KEY or GOOGLE_SEARCH_ENGINE_ID in .env")

GOOGLE_API = Settings.GOOGLE_API_URL


def filter_by_relevance(
    images: list[dict], query_keywords: list[str], min_score: float = 0.25
) -> list[dict]:
    """
    Filtra imágenes comparando su descripción/snippet (inglés) contra las
    keywords de búsqueda (inglés).
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
        return set(doc.get("id") for doc in db["used_google_ids"].find({}, {"id": 1}))
    except Exception:
        return set()


def add_used_id(img_id: str):
    try:
        from src.shared.adapters.mongo_db import get_database
        db = get_database()
        db["used_google_ids"].update_one({"id": img_id}, {"$set": {"id": img_id}}, upsert=True)
    except Exception:
        pass


class GoogleImagesFetcher:
    def __init__(self, mode: str = "news"):
        self.mode = mode

    def _search_images(self, query: str, limit: int = 10) -> list[dict]:
        if not GOOGLE_API_KEY or not GOOGLE_CX:
            return []
        used_ids = get_used_ids()
        try:
            params = {
                "key": GOOGLE_API_KEY,
                "cx": GOOGLE_CX,
                "q": query,
                "searchType": "image",
                "num": limit,
            }
            resp = requests.get(GOOGLE_API, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"[GOOGLE] API error: {resp.status_code}")
                return []
            images = []
            for img in resp.json().get("items", []):
                link = img.get("link")
                if link and link not in used_ids:
                    images.append({
                        "id": str(hash(link))[:20],
                        "url": link,
                        "thumbnail": img.get("image", {}).get("thumbnailLink"),
                        "description": img.get("snippet") or img.get("title", ""),
                    })
            return images
        except Exception as e:
            logger.warning(f"[GOOGLE] Search error: {e}")
            return []

    def fetch_for_posts(self, posts: list) -> list:
        from src.shared.adapters.image_query_generator import generar_keywords_visuales_con_llm

        changed = 0
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

            content = post.get("content") or post.get("article") or ""

            keywords = generar_keywords_visuales_con_llm(title, content)
            if not keywords:
                logger.warning(f"[GOOGLE] No keywords for '{title[:40]}'")
                continue

            query = " ".join(keywords[:4])
            raw_images = self._search_images(query, limit=10)
            relevant = filter_by_relevance(raw_images, keywords)

            if not relevant:
                logger.warning(f"[GOOGLE] No relevant images for '{title[:40]}' (query: {query})")
                continue

            selected = relevant[0]
            img_url = selected.get("url")
            img_id = selected.get("id")

            post["google_image"] = img_url
            post["google_image_url"] = img_url
            post["image_credit"] = post.get("image_credit") or "Google Images"
            post["alt_text"] = (selected.get("description") or title)[:200]

            if img_id:
                add_used_id(img_id)

            changed += 1
            score = selected.get("_relevance_score", 0.0)
            logger.info(f"[GOOGLE] ✅ {title[:40]}: {img_url[:40] if img_url else ''} (score={score:.2f})")

        logger.info(f"[GOOGLE] {changed} images assigned")
        return posts

    def fetch_from_mongo(self) -> int:
        try:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
            coll = db["generated_posts"]
            posts = list(coll.find({}))
            if not posts:
                logger.warning("[GOOGLE] No posts to enrich")
                return 0
            self.fetch_for_posts(posts)
            for post in posts:
                post_id = post.pop("_id", None)
                if post_id:
                    coll.update_one({"_id": post_id}, {"$set": post})
            return len(posts)
        except Exception as e:
            logger.error(f"[GOOGLE] Error: {e}")
            return 0


def run(mode: str = "news") -> int:
    logger.info(f"[GOOGLE] Running (mode: {mode})")
    return GoogleImagesFetcher(mode=mode).fetch_from_mongo()


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "news")
