import os
import re
import requests
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Dict, Optional

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot")

load_dotenv(override=True)

# Use Settings for all configuration
PAGE_ID = Settings.FACEBOOK_PAGE_ID
PAGE_TOKEN = Settings.FACEBOOK_PAGE_ACCESS_TOKEN
APP_ID = Settings.FACEBOOK_APP_ID
APP_SECRET = Settings.FACEBOOK_APP_SECRET

if not PAGE_ID or not PAGE_TOKEN:
    raise ValueError("Facebook credentials not found in .env")


def validate_image_url(url: str, max_size_mb: int = 10) -> bool:
    """Valida imagen antes de subir."""
    try:
        resp = requests.get(url, stream=True, timeout=15)
        if resp.status_code != 200:
            return False
        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return False
        size = int(resp.headers.get("Content-Length", 0))
        if size and size > max_size_mb * 1024 * 1024:
            logger.warning(
                f"[FACEBOOK] Imagen demasiado grande: {size / 1024 / 1024:.2f} MB"
            )
            return False
        return True
    except Exception as e:
        logger.warning(f"[FACEBOOK] Error validando imagen: {e}")
        return False


class FacebookPublisher:
    """Publisher para Facebook."""

    def _load_posts_from_mongo(self) -> List[Dict]:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_posts"]
            posts = list(coll.find({}))
            for p in posts:
                p.pop("_id", None)
            return posts
        except Exception as e:
            logger.error(f"[FACEBOOK] Error cargando posts: {e}")
            return []

    def _save_post(self, post: Dict) -> bool:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_posts"]
            url = post.get("url")
            if url:
                coll.update_one({"url": url}, {"$set": post})
            return True
        except Exception as e:
            logger.error(f"[FACEBOOK] Error guardando post: {e}")
            return False

    def publish_posts(
        self, posts: List[Dict] = None, articles: List[Dict] = None
    ) -> Dict:
        """Publica posts en Facebook."""
        if posts is None:
            posts = self._load_posts_from_mongo()

        if not posts:
            logger.warning("[FACEBOOK] No hay posts para publicar")
            return {"status": "warning", "message": "No hay posts"}

        logger.info(f"[FACEBOOK] Publicando {len(posts)} posts")

        published = 0
        errors = 0

        for idx, post in enumerate(posts):
            if post.get("facebook_url"):
                logger.warning(
                    f"[FACEBOOK] Post ya publicado: {post.get('title', '')[:60]}..."
                )
                continue

            # Usar solo el contenido del post (tweet)
            tweet = (post.get("tweet") or "").strip()
            if not tweet:
                logger.warning(
                    f"[FACEBOOK] Post sin tweet: {post.get('title', '')[:60]}..."
                )
                continue

            title_es = (post.get("title_es") or "").strip()
            title_orig = (post.get("title") or "Noticia destacada").strip()
            title = title_es or title_orig

            hashtags = post.get("hashtags", [])
            hashtags_str = " ".join(hashtags) if hashtags else ""

            # Formato simple: título + tweet + hashtags
            message_text = f"📌 {title}\n\n{tweet}"
            if hashtags_str:
                message_text += f"\n\n{hashtags_str}"

            wp_url = (post.get("wp_url") or "").strip()
            if wp_url:
                message_text += f"\n\nMás info: {wp_url}"

            image_url = (post.get("image_url") or "").strip()
            if (
                image_url
                and image_url.startswith("http")
                and validate_image_url(image_url)
            ):
                endpoint = f"{Settings.FACEBOOK_GRAPH_API_BASE}/{Settings.FACEBOOK_GRAPH_API_VERSION}/{PAGE_ID}/photos"
                payload = {
                    "url": image_url,
                    "caption": message_text,
                    "access_token": PAGE_TOKEN,
                }
            else:
                endpoint = f"{Settings.FACEBOOK_GRAPH_API_BASE}/{Settings.FACEBOOK_GRAPH_API_VERSION}/{PAGE_ID}/feed"
                payload = {"message": message_text, "access_token": PAGE_TOKEN}

            logger.info(f"[FACEBOOK] Publicando en {endpoint}")
            resp = requests.post(endpoint, data=payload)

            if resp.status_code != 200:
                logger.error(f"[FACEBOOK] Error: {resp.status_code} {resp.text}")
                errors += 1
                continue

            fb_resp = resp.json()
            post_id = fb_resp.get("id")
            post_url = f"https://www.facebook.com/{post_id}" if post_id else None

            logger.info(f"[FACEBOOK] ✅Publicado: {post_url}")
            post["facebook_url"] = post_url
            self._save_post(post)
            published += 1

        return {
            "status": "success",
            "published": published,
            "errors": errors,
            "total": len(posts),
        }


def run() -> Dict:
    """Función principal."""
    publisher = FacebookPublisher()
    return publisher.publish_posts()


if __name__ == "__main__":
    result = run()
    print(f"[FACEBOOK] Resultado: {result}")
