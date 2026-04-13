import os
import requests
from pathlib import Path
from hashlib import md5

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot")

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
            # Si ya tiene imagen válida (no fallback), no sobrescribir
            if post.get("image_url") and "nbes.blog" not in post.get("image_url", ""):
                # Verificar que la imagen sea accesible (no 403 de sitios con protección)
                current_url = post.get("image_url", "")
                if not self._is_accessible_image(current_url):
                    logger.warning(
                        f"[IMAGES] Imagen actual no accesible (403): {current_url[:60]}... "
                        f"Buscando alternativa"
                    )
                    post.pop("image_url", None)
                else:
                    logger.info(
                        f"[IMAGES] {post.get('title', '')[:40]}: ya tiene imagen → {current_url[:50]}"
                    )
                    continue

            image_urls = get_image_urls(post)
            assigned = False

            # Priorizar Unsplash sobre Google Images (Google suele dar 403)
            # Reordenar: unsplash primero, google después
            unsplash_urls = [u for u in image_urls if "unsplash" in (u or "").lower()]
            other_urls = [u for u in image_urls if "unsplash" not in (u or "").lower()]
            priority_urls = unsplash_urls + other_urls

            for url in priority_urls:
                if url and self._is_accessible_image(url):
                    post["image_url"] = url
                    post["image_credit"] = post.get("image_credit") or "Unsplash"
                    post["alt_text"] = post.get("alt_text") or post.get("title", "")[:100]
                    post["image_path"] = None
                    assigned = True
                    changed += 1
                    break
                elif url:
                    logger.debug(f"[IMAGES] Imagen no accesible, saltando: {url[:60]}...")

            if not assigned:
                orig_url = post.get("url") or post.get("original_url")
                if orig_url:
                    extracted = extract_image(orig_url)
                    if extracted and self._is_accessible_image(extracted):
                        post["image_url"] = extracted
                        post["image_credit"] = "Sitio web original"
                        post["alt_text"] = post.get("alt_text") or post.get("title", "")[:100]
                        post["image_path"] = None
                        assigned = True
                        changed += 1

            if not assigned:
                assign_fallback(post)

            logger.info(
                f"[IMAGES] {post.get('title', '')[:40]}: {post.get('image_url', 'fallback')[:50]}"
            )

        logger.info(f"[IMAGES] {changed} posts enriched")
        return posts

    def _is_accessible_image(self, url: str, timeout: int = 8) -> bool:
        """Verifica que la URL de imagen sea realmente accesible y descargable.

        Hace GET con Range header para descargar solo los primeros bytes,
        evitando falsos positivos de HEAD con redirects que luego dan 403.
        """
        if not url:
            return False
        try:
            # GET parcial: descargar solo primeros 1KB para validar
            headers = {"Range": "bytes=0-1023"}
            resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
            # 206 = Partial Content (éxito), 200 = OK completo
            if resp.status_code in (200, 206):
                # Verificar que es realmente una imagen
                content_type = resp.headers.get("Content-Type", "")
                return "image" in content_type or resp.status_code == 206
            return False
        except Exception:
            return False

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

    def enrich_articles_from_mongo(self) -> int:
        """Enriquece también los artículos generados con imágenes."""
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            articles_coll = db["generated_articles"]
            posts_coll = db["generated_posts"]
            
            articles = list(articles_coll.find({}))

            if not articles:
                logger.warning("[IMAGES] No hay artículos para enriquecer")
                return 0

            # Primero, intentar heredar imágenes de posts que tengan el mismo original_url
            for article in articles:
                original_url = article.get("original_url")
                if original_url:
                    # Buscar si hay un post con la misma URL original
                    matching_post = posts_coll.find_one({"original_url": original_url})
                    if not matching_post:
                        # También buscar por url
                        matching_post = posts_coll.find_one({"url": original_url})
                    
                    if matching_post:
                        # Heredar campos de imagen del post
                        if matching_post.get("image_url"):
                            article["image_url"] = matching_post["image_url"]
                            article["image_credit"] = matching_post.get("image_credit", "Unsplash")
                            article["alt_text"] = matching_post.get("alt_text") or article.get("title", "")[:100]
                            article["image_path"] = None
                            logger.info(f"[IMAGES] Imagen heredada del post para: {article.get('title', '')[:50]}")
                            continue

            # Luego, enriquecer los que aún no tengan imagen
            self.enrich(articles)

            for article in articles:
                article_id = article.get("_id")
                if article_id:
                    article.pop("_id", None)
                    articles_coll.update_one({"_id": article_id}, {"$set": article})

            return len(articles)

        except Exception as e:
            logger.error(f"[IMAGES] Error enrich articles from MongoDB: {e}")
            return 0


def run(mode: str = "news") -> int:
    logger.info(f"[IMAGES] Ejecutando enrich_with_images (modo: {mode})")
    enricher = ImageEnricher(mode=mode)
    posts_count = enricher.enrich_from_mongo()
    articles_count = enricher.enrich_articles_from_mongo()
    logger.info(f"[IMAGES] Enriquecimiento completado: {posts_count} posts, {articles_count} artículos")
    return posts_count + articles_count


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "news"
    run(mode)
