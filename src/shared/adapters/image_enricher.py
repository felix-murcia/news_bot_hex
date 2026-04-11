import os
import logging
import requests
from pathlib import Path
from hashlib import md5

from config.settings import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")

DEF_LOGO_URL = Settings.WP_DEFAULT_IMAGE_URL
IMG_DIR = Settings.IMAGES_DIR
IMG_DIR.mkdir(parents=True, exist_ok=True)


def extract_image(url: str) -> str | None:
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Referer": url,
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")

        for prop in ["og:image", "twitter:image", "image"]:
            tag = soup.find("meta", property=prop) or soup.find(
                "meta", attrs={"name": prop}
            )
            if tag:
                content = tag.get("content")
                if content:
                    return str(content)

        img = soup.find("img")
        if img:
            src = img.get("src")
            if src:
                return str(src)

    except Exception as e:
        logger.warning(f"[IMAGES] No se pudo extraer imagen de {url}: {e}")
    return None


def download_image(url: str) -> str | None:
    try:
        ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
        filename = md5(url.encode("utf-8")).hexdigest() + ext
        dest_path = IMG_DIR / filename

        if dest_path.exists():
            logger.info(f"[IMAGES] Imagen ya descargada: {dest_path}")
            return str(dest_path)

        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            return str(dest_path)
        else:
            logger.warning(
                f"[IMAGES] No se pudo descargar {url} (status {resp.status_code})"
            )
    except Exception as e:
        logger.warning(f"[IMAGES] Error descargando {url}: {e}")
    return None


def get_image_urls(post: dict) -> list:
    def norm(url):
        if not url:
            return None
        if "nbes.blog" in url or url == DEF_LOGO_URL:
            return None
        return url

    candidates = [
        post.get("unsplash_image"),
        post.get("unsplash_image_url"),
        post.get("google_image"),
        post.get("google_image_url"),
        post.get("image_url"),
        post.get("featured_image"),
        post.get("og_image"),
    ]
    return [c for c in candidates if norm(c)]


def assign_fallback(post: dict):
    post["image_url"] = DEF_LOGO_URL
    post["image_credit"] = "NBES"
    post["alt_text"] = "Logo NBES"
    post["image_path"] = None
    logger.warning(f"[IMAGES] Usando logo NBES como fallback")


class ImageEnricher:
    def __init__(self, mode: str = "news"):
        self.mode = mode

    def enrich(self, posts: list) -> list:
        changed = 0

        for post in posts:
            image_urls = get_image_urls(post)
            assigned = False

            for url in image_urls:
                if url:
                    post["image_url"] = url
                    assigned = True
                    changed += 1
                    break

            if not assigned:
                orig_url = post.get("url") or post.get("original_url")
                if orig_url:
                    extracted = extract_image(orig_url)
                    if extracted:
                        post["image_url"] = extracted
                        assigned = True
                        changed += 1

            if not assigned:
                assign_fallback(post)

            logger.info(
                f"[IMAGES] {post.get('title', '')[:40]}: {post.get('image_url', 'fallback')[:50]}"
            )

        logger.info(f"[IMAGES] {changed} posts enriched")
        return posts

    def enrich_from_mongo(self) -> int:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_posts"]
            posts = list(coll.find({}))

            if not posts:
                logger.warning("[IMAGES] No hay posts para enriquecer")
                return 0

            self.enrich(posts)

            for post in posts:
                post_id = post.get("_id")
                if post_id:
                    post.pop("_id", None)
                    coll.update_one({"_id": post_id}, {"$set": post})

            return len(posts)

        except Exception as e:
            logger.error(f"[IMAGES] Error enrich from MongoDB: {e}")
            return 0


def run(mode: str = "news") -> int:
    logger.info(f"[IMAGES] Ejecutando enrich_with_images (modo: {mode})")
    enricher = ImageEnricher(mode=mode)
    return enricher.enrich_from_mongo()


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "news"
    run(mode)
