import os
import requests
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Optional
from requests.adapters import HTTPAdapter, Retry
from src.logging_config import get_logger

logger = get_logger("news_bot")

load_dotenv()
MASTODON_INSTANCE = os.getenv("MASTODON_INSTANCE", "").strip().rstrip("/")
MASTODON_ACCESS_TOKEN = os.getenv("MASTODON_TOKEN")

if not MASTODON_INSTANCE or not MASTODON_ACCESS_TOKEN:
    raise RuntimeError(
        "Faltan variables de entorno: MASTODON_INSTANCE o MASTODON_TOKEN"
    )

MASTODON_API_BASE = f"https://{MASTODON_INSTANCE}"

session = requests.Session()
retries = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))


def publish_post(
    content: str,
    url: Optional[str] = None,
    image_path: Optional[str] = None,
    image_url: Optional[str] = None,
    hashtags: Optional[List[str]] = None,
) -> Optional[str]:
    """Publica un post en Mastodon."""
    try:
        headers = {"Authorization": f"Bearer {MASTODON_ACCESS_TOKEN}"}

        status_text = content.strip()
        if hashtags:
            status_text += f"\n\n{' '.join(hashtags)}"
        if url:
            status_text += f"\n\nMás info: {url}"
        if len(status_text) > 500:
            status_text = status_text[:497] + "..."

        logger.info(f"[MASTODON] Toot: {status_text[:100]}...")

        media_ids = []

        if image_path and Path(image_path).exists():
            try:
                logger.info(f"[MASTODON] Subiendo imagen local: {image_path}")
                with open(image_path, "rb") as f:
                    files = {"file": ("image.jpg", f, "image/jpeg")}
                    media_resp = requests.post(
                        f"{MASTODON_API_BASE}/api/v2/media",
                        headers=headers,
                        files=files,
                        timeout=30,
                    )
                if media_resp.status_code in (200, 202):
                    media_id = media_resp.json().get("id")
                    if media_id:
                        media_ids.append(str(media_id))
                        logger.info(
                            f"[MASTODON] Imagen local subida, media_id={media_id}"
                        )
            except Exception as e:
                logger.warning(f"[MASTODON] Error subiendo imagen local: {e}")

        elif image_url:
            try:
                logger.info(f"[MASTODON] Descargando imagen remota: {image_url}")
                img_resp = session.get(
                    image_url, timeout=60, headers={"User-Agent": "Mozilla/5.0"}
                )
                img_resp.raise_for_status()
                files = {"file": ("image.jpg", img_resp.content, "image/jpeg")}
                media_resp = requests.post(
                    f"{MASTODON_API_BASE}/api/v2/media",
                    headers=headers,
                    files=files,
                    timeout=30,
                )
                if media_resp.status_code in (200, 202):
                    media_id = media_resp.json().get("id")
                    if media_id:
                        media_ids.append(str(media_id))
                        logger.info(
                            f"[MASTODON] Imagen remota subida, media_id={media_id}"
                        )
            except Exception as e:
                logger.warning(f"[MASTODON] Error con imagen remota: {e}")

        payload: Dict = {"status": status_text}
        if media_ids:
            payload["media_ids"] = media_ids  # type: ignore[assignment]

        logger.info("[MASTODON] Publicando toot...")
        resp = requests.post(
            f"{MASTODON_API_BASE}/api/v1/statuses",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )

        if resp.status_code == 200:
            post_url = resp.json().get("url")
            logger.info(f"[MASTODON] ✅Publicado: {post_url}")
            return post_url
        else:
            logger.error(f"[MASTODON] Error: {resp.status_code} {resp.text}")
            return None

    except Exception as e:
        logger.error(f"[MASTODON] Excepción: {e}")
        return None


class MastodonPublisher:
    """Publisher para Mastodon."""

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
            logger.error(f"[MASTODON] Error cargando posts: {e}")
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
            logger.error(f"[MASTODON] Error guardando post: {e}")
            return False

    def publish_posts(self, posts: Optional[List[Dict]] = None) -> Dict:
        """Publica posts en Mastodon."""
        if posts is None:
            posts = self._load_posts_from_mongo()

        if not posts:
            logger.warning("[MASTODON] No hay posts para publicar")
            return {"status": "warning", "message": "No hay posts"}

        logger.info(f"[MASTODON] Publicando {len(posts)} posts")

        published = 0
        errors = 0

        for idx, post in enumerate(posts):
            content = (post.get("tweet") or "").strip()
            if not content:
                logger.warning(f"[MASTODON] Post sin contenido idx={idx}")
                continue

            if post.get("mastodon_url"):
                logger.warning(f"[MASTODON] Post ya publicado: {content[:60]}...")
                continue

            wp_url = (post.get("wp_url") or "").strip()
            orig_url = (post.get("url") or "").strip()
            url = wp_url or orig_url

            image_path = post.get("image_path") or None
            image_url = (post.get("image_url") or "").strip()
            hashtags = post.get("hashtags") or []

            post_url = publish_post(
                content, url or None, image_path, image_url or None, hashtags
            )

            if post_url:
                logger.info(f"[MASTODON] ✅Publicado: {post_url}")
                post["mastodon_url"] = post_url
                self._save_post(post)
                published += 1
            else:
                logger.error(f"[MASTODON] Error al publicar: {content[:60]}")
                errors += 1

        return {
            "status": "success",
            "published": published,
            "errors": errors,
            "total": len(posts),
        }


def run() -> Dict:
    """Función principal."""
    publisher = MastodonPublisher()
    return publisher.publish_posts()


if __name__ == "__main__":
    result = run()
    print(f"[MASTODON] Resultado: {result}")
