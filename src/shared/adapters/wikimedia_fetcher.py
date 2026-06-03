import re
import requests

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot")

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _search_images(query: str, limit: int = 10) -> list[dict]:
    try:
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size",
            "iiurlwidth": 1200,
            "format": "json",
            "origin": "*",
        }
        resp = requests.get(WIKIMEDIA_API, params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"[WIKIMEDIA] API error: {resp.status_code}")
            return []

        pages = resp.json().get("query", {}).get("pages", {})
        images = []
        for page in pages.values():
            title = page.get("title", "")
            ext = "." + title.rsplit(".", 1)[-1].lower() if "." in title else ""
            if ext not in _PHOTO_EXTENSIONS:
                continue

            imageinfo = (page.get("imageinfo") or [{}])[0]
            url = imageinfo.get("url", "")
            if not url:
                continue

            meta = imageinfo.get("extmetadata", {})
            description = _strip_html(meta.get("ImageDescription", {}).get("value", ""))
            artist = _strip_html(meta.get("Artist", {}).get("value", ""))
            license_name = meta.get("LicenseShortName", {}).get("value", "Wikimedia Commons")

            if not description:
                name = title.replace("File:", "").rsplit(".", 1)[0]
                description = re.sub(r"[_\-]+", " ", name).strip()

            credit = f"{artist} / {license_name}".strip(" /") if artist else license_name

            images.append({
                "id": title,
                "url": url,
                "description": description,
                "credit": credit,
            })
        return images
    except Exception as e:
        logger.warning(f"[WIKIMEDIA] Search error: {e}")
        return []


def _filter_by_relevance(images: list[dict], keywords: list[str], min_score: float = 0.25) -> list[dict]:
    keyword_words = {w.lower() for kw in keywords for w in re.findall(r"\b[a-z]{3,}\b", kw.lower())}

    scored = []
    for img in images:
        description = (img.get("description") or "").lower()
        desc_words = set(re.findall(r"\b[a-z]{3,}\b", description))
        if not desc_words:
            continue
        common = desc_words.intersection(keyword_words)
        union = desc_words.union(keyword_words)
        score = len(common) / len(union) if union else 0.0
        img["_relevance_score"] = score
        if score >= min_score:
            scored.append(img)

    scored.sort(key=lambda x: x["_relevance_score"], reverse=True)
    return scored


class WikimediaFetcher:
    def fetch_for_posts(self, posts: list) -> list:
        from src.shared.adapters.image_query_generator import generar_keywords_visuales_con_llm

        fallback_url = Settings.WP_DEFAULT_IMAGE_URL
        changed = 0

        for post in posts:
            if post.get("wikimedia_image"):
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
                logger.warning(f"[WIKIMEDIA] No keywords for '{title[:40]}'")
                continue

            query = " ".join(keywords[:4])
            raw_images = _search_images(query, limit=10)
            relevant = _filter_by_relevance(raw_images, keywords)

            if not relevant:
                logger.warning(f"[WIKIMEDIA] No relevant images for '{title[:40]}' (query: {query})")
                continue

            selected = relevant[0]
            url = selected["url"]
            score = selected.get("_relevance_score", 0.0)

            post["wikimedia_image"] = url
            post["image_url"] = url
            post["image_credit"] = selected["credit"]
            post["alt_text"] = selected["description"][:200]

            changed += 1
            logger.info(f"[WIKIMEDIA] ✅ {title[:40]}: {url[:50]} (score={score:.2f})")

        logger.info(f"[WIKIMEDIA] {changed} images assigned")
        return posts

    def fetch_from_mongo(self) -> int:
        try:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
            coll = db["generated_posts"]
            posts = list(coll.find({}))
            if not posts:
                logger.warning("[WIKIMEDIA] No posts to enrich")
                return 0
            self.fetch_for_posts(posts)
            for post in posts:
                post_id = post.pop("_id", None)
                if post_id:
                    coll.update_one({"_id": post_id}, {"$set": post})
            return len(posts)
        except Exception as e:
            logger.error(f"[WIKIMEDIA] Error: {e}")
            return 0


def run() -> int:
    logger.info("[WIKIMEDIA] Running")
    return WikimediaFetcher().fetch_from_mongo()


if __name__ == "__main__":
    run()
