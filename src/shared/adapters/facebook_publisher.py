import os
import re
import logging
import requests
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")

load_dotenv()
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
PAGE_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
APP_ID = os.getenv("FACEBOOK_APP_ID")
APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")

if not PAGE_ID or not PAGE_TOKEN:
    raise ValueError("Credenciales de Facebook no encontradas en .env")


def validate_token(token: str) -> bool:
    """Valida el token de Facebook."""
    debug_url = f"https://graph.facebook.com/debug_token?input_token={token}&access_token={APP_ID}|{APP_SECRET}"
    resp = requests.get(debug_url)
    if resp.status_code != 200:
        logger.warning(f"[FACEBOOK] Error al validar token: {resp.text}")
        return False
    data = resp.json().get("data", {})
    if not data.get("is_valid"):
        logger.error(f"[FACEBOOK] Token inválido o caducado: {data}")
        return False
    exp = data.get("expires_at")
    if exp:
        exp_date = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[FACEBOOK] Token válido. Expira: {exp_date}")
    else:
        logger.info("[FACEBOOK] Token válido")
    return True


if not validate_token(PAGE_TOKEN):
    raise SystemExit("El token de página no es válido")


def clean_article_text(html: str, max_chars: int = 5000) -> str:
    """Limpia y recorta texto del artículo."""
    if not html:
        return ""
    html = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = text.strip()
    filtros = [
        "Lee también más noticias",
        "Síguenos en:",
        "Bluesky",
        "Mastodon",
        "Facebook",
    ]
    text = "\n".join(
        line
        for line in text.splitlines()
        if not any(f in line for f in filtros)
        and not line.strip().startswith("Fuente:")
    )
    if len(text) > max_chars:
        cutoff = text.rfind(" ", 0, max_chars)
        if cutoff == -1:
            cutoff = max_chars
        text = text[:cutoff].strip()
    return text


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

    def _load_articles_from_mongo(self) -> List[Dict]:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_articles"]
            articles = list(coll.find({}))
            for a in articles:
                a.pop("_id", None)
            return articles
        except Exception as e:
            logger.error(f"[FACEBOOK] Error cargando artículos: {e}")
            return []

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
        if articles is None:
            articles = self._load_articles_from_mongo()

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

            art = (
                articles[idx]
                if idx < len(articles) and isinstance(articles[idx], dict)
                else None
            )
            content_text = (
                clean_article_text(art["content"])
                if art and art.get("content")
                else (post.get("tweet") or "").strip()
            )

            title_es = (post.get("title_es") or "").strip()
            title_orig = (post.get("title") or "Noticia destacada").strip()
            title = title_es or title_orig

            hashtags = post.get("hashtags", [])
            hashtags_str = " ".join(hashtags) if hashtags else ""

            message_text = f"📌 **{title}**\n\n{content_text}"
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
                endpoint = f"https://graph.facebook.com/v23.0/{PAGE_ID}/photos"
                payload = {
                    "url": image_url,
                    "caption": message_text,
                    "access_token": PAGE_TOKEN,
                }
            else:
                endpoint = f"https://graph.facebook.com/v23.0/{PAGE_ID}/feed"
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
