import os
import re
import requests
from io import BytesIO
from PIL import Image
from atproto import Client, models
from dotenv import load_dotenv
from typing import List, Dict, Optional
import regex
from src.logging_config import get_logger

logger = get_logger("news_bot")

load_dotenv()
HANDLE = os.getenv("BLUESKY_HANDLE")
PASSWORD = os.getenv("BLUESKY_PASSWORD")

POST_LIMITS = {
    "bluesky": 300,
    "twitter": 280,
    "mastodon": 500,
    "facebook": 63206,
}


def get_client() -> Client:
    """Obtiene cliente Bluesky autenticado."""
    if not HANDLE or not PASSWORD:
        raise ValueError("Credenciales Bluesky no encontradas en .env")
    client = Client()
    client.login(HANDLE, PASSWORD)
    logger.info("Cliente Bluesky inicializado y autenticado")
    return client


def compress_image_from_url(url: str, max_kb: int = 950) -> BytesIO:
    """Descarga y comprime imagen desde URL."""
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    img = Image.open(BytesIO(resp.content)).convert("RGB")

    quality = 85
    while True:
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        size_kb = buffer.tell() / 1024
        if size_kb <= max_kb or quality <= 30:
            break
        quality -= 5
    buffer.seek(0)
    return buffer


def truncate_graphemes(text: str, limit: int) -> str:
    """Trunca texto a número de grafemas."""
    graphemes = regex.findall(r"\X", text)
    if len(graphemes) <= limit:
        return text
    return "".join(graphemes[: limit - 1]) + "…"


def build_hashtag_facets(text: str) -> List:
    """Construye facets para hashtags."""
    facets = []
    for match in regex.finditer(r"#\w+", text):
        start_char, end_char = match.span()
        start_byte = len(text[:start_char].encode("utf-8"))
        end_byte = len(text[:end_char].encode("utf-8"))

        facets.append(
            models.AppBskyRichtextFacet.Main(
                features=[models.AppBskyRichtextFacet.Tag(tag=match.group()[1:])],
                index=models.AppBskyRichtextFacet.ByteSlice(
                    byte_start=start_byte, byte_end=end_byte
                ),
            )
        )
    return facets


def summarize_for_bluesky(text: str, limit: int = 300) -> str:
    """Resume texto para Bluesky."""
    graphemes = regex.findall(r"\X", text)
    if len(graphemes) <= limit:
        return text
    return "".join(graphemes[:limit]).strip()


class BlueskyPublisher:
    """Publisher para Bluesky."""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_client()
        return self._client

    def _load_posts_from_mongo(self) -> List[Dict]:
        """Carga posts desde MongoDB."""
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_posts"]
            posts = list(coll.find({}))
            for p in posts:
                p.pop("_id", None)
            return posts
        except Exception as e:
            logger.error(f"[BLUESKY] Error cargando posts: {e}")
            return []

    def _save_post(self, post: Dict) -> bool:
        """Guarda post actualizado en MongoDB."""
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_posts"]
            url = post.get("url")
            if url:
                coll.update_one({"url": url}, {"$set": post})
            return True
        except Exception as e:
            logger.error(f"[BLUESKY] Error guardando post: {e}")
            return False

    def publish_posts(self, posts: Optional[List[Dict]] = None) -> Dict:
        """Publica posts en Bluesky."""
        if posts is None:
            posts = self._load_posts_from_mongo()

        if not posts:
            logger.warning("[BLUESKY] No hay posts para publicar")
            return {"status": "warning", "message": "No hay posts"}

        logger.info(f"[BLUESKY] Publicando {len(posts)} posts")

        published = 0
        errors = 0

        for idx, post in enumerate(posts):
            text_base = (post.get("tweet") or "").strip()
            wp_url = (post.get("wp_url") or "").strip()
            orig_url = (post.get("url") or "").strip()
            url = wp_url or orig_url

            if not text_base and not url:
                logger.warning(f"[BLUESKY] Post inválido idx={idx}, omitido")
                continue

            if post.get("bluesky_url"):
                logger.warning(f"[BLUESKY] Post ya publicado: {text_base[:60]}...")
                continue

            max_len = POST_LIMITS.get("bluesky", 300)

            cleaned_text = text_base
            cleaned_text = re.sub(
                r"\[HASHTAGS\]", "", cleaned_text, flags=re.IGNORECASE
            )
            cleaned_text = re.sub(
                r"^Hashtags:.*$", "", cleaned_text, flags=re.MULTILINE
            )
            cleaned_text = re.sub(r"^\s*#\w+\s*$", "", cleaned_text, flags=re.MULTILINE)
            cleaned_text = cleaned_text.strip()

            has_hashtags = bool(re.search(r"#\w+", cleaned_text))

            safe_content = summarize_for_bluesky(cleaned_text, max_len)

            facets = build_hashtag_facets(safe_content)
            embed = None
            thumb_blob = None

            image_url = (post.get("image_url") or "").strip()
            if url and image_url:
                try:
                    compressed = compress_image_from_url(image_url)
                    compressed.seek(0)
                    thumb_blob = self.client.com.atproto.repo.upload_blob(
                        compressed.read()
                    ).blob
                except Exception as e:
                    logger.warning(f"[BLUESKY] Error con miniatura: {e}")

            if url:
                embed = models.AppBskyEmbedExternal.Main(
                    external=models.AppBskyEmbedExternal.External(
                        uri=url,
                        title="Noticia desarrollada",
                        description="",
                        thumb=thumb_blob,
                    )
                )

            try:
                post_uri = self.client.send_post(
                    text=safe_content, embed=embed, facets=facets
                )

                if isinstance(post_uri, str):
                    rkey = post_uri.split("/")[-1]
                    post_url = f"https://bsky.app/profile/{HANDLE}/post/{rkey}"
                else:
                    post_url = str(post_uri)

                logger.info(f"[BLUESKY] ✅Publicado: {post_url}")
                post["bluesky_url"] = post_url
                self._save_post(post)
                published += 1

            except Exception as e:
                logger.error(f"[BLUESKY] Error publicando: {e}")
                errors += 1

        return {
            "status": "success",
            "published": published,
            "errors": errors,
            "total": len(posts),
        }


def run() -> Dict:
    """Función principal."""
    publisher = BlueskyPublisher()
    return publisher.publish_posts()


if __name__ == "__main__":
    result = run()
    print(f"[BLUESKY] Resultado: {result}")
