import os
import requests
from pathlib import Path
from typing import List, Dict, Optional
from io import BytesIO

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot")


def validate_wp_token() -> bool:
    """
    Validate WordPress JWT token before starting any pipeline.

    Returns:
        True if token is valid, False otherwise.

    Raises:
        RuntimeError: If token validation fails.
    """
    if not Settings.WP_HOSTING_JWT_TOKEN:
        logger.error("[WP-VALIDATE] WP_HOSTING_JWT_TOKEN not configured")
        raise RuntimeError("WordPress JWT token not configured")

    try:
        headers = {
            "Authorization": f"Bearer {Settings.WP_HOSTING_JWT_TOKEN}",
            "User-Agent": "Mozilla/5.0 (compatible; NBESBot/1.0)",
        }

        # Test with a simple GET request to verify token
        resp = requests.get(
            f"{Settings.WP_API_URL}/posts?per_page=1",
            headers=headers,
            timeout=10,
        )

        if resp.status_code == 200:
            logger.info("[WP-VALIDATE] WordPress token is valid")
            return True
        elif resp.status_code in (401, 403):
            error_detail = resp.text[:200] if resp.text else "No details"
            logger.error(
                f"[WP-VALIDATE] WordPress token expired or invalid ({resp.status_code}): {error_detail}"
            )
            raise RuntimeError(
                f"WordPress JWT token expired or invalid (HTTP {resp.status_code}). "
                "Please generate a new token from your WordPress admin panel."
            )
        else:
            logger.warning(f"[WP-VALIDATE] Unexpected response: {resp.status_code}")
            # Don't fail on non-auth errors (could be network issues)
            return True

    except requests.exceptions.RequestException as e:
        logger.error(f"[WP-VALIDATE] Connection error: {e}")
        raise RuntimeError(f"Cannot connect to WordPress API: {e}")


def get_headers():
    """Get authentication headers for WordPress API. Auto-refreshes token if needed."""
    if not Settings.WP_HOSTING_JWT_TOKEN:
        # Try to auto-refresh before failing
        try:
            from src.shared.adapters.wordpress_token_manager import get_valid_wp_token

            get_valid_wp_token()
            logger.info("[HOSTING] WordPress token auto-refreshed")
        except Exception as e:
            logger.warning(f"[HOSTING] Token refresh failed: {e}")
            raise RuntimeError(
                "WP_HOSTING_JWT_TOKEN not configured and auto-refresh failed. "
                "Check WP_USER and WP_PASSWORD in .env"
            )

    return {
        "Authorization": f"Bearer {Settings.WP_HOSTING_JWT_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; NBESBot/1.0)",
    }


def rest_url(endpoint: str) -> str:
    """Build WordPress REST API URL for an endpoint."""
    return f"{Settings.WP_API_URL}/{endpoint}"


def upload_image(
    image_path: str, credit: Optional[str] = None, alt_text: Optional[str] = None
) -> Optional[int]:
    try:
        headers = get_headers()
        headers.pop("Content-Type", None)
        with open(image_path, "rb") as f:
            files = {"file": (os.path.basename(image_path), f)}
            logger.info(f"[HOSTING] Subiendo imagen: {image_path}")
            resp = requests.post(
                rest_url("media"), headers=headers, files=files, timeout=30
            )
        if resp.status_code in (200, 201):
            media_id = resp.json().get("id")
            logger.info(f"[HOSTING] Imagen subida, ID={media_id}")
            if media_id and (credit or alt_text):
                try:
                    meta_payload = {}
                    if alt_text:
                        meta_payload["alt_text"] = alt_text
                    if credit:
                        meta_payload["caption"] = credit
                        meta_payload["description"] = credit
                    requests.post(
                        rest_url(f"media/{media_id}"),
                        headers=get_headers(),
                        json=meta_payload,
                        timeout=15,
                    )
                except Exception as e:
                    logger.warning(f"[HOSTING] No se pudo asignar créditos: {e}")
            return int(media_id)
        else:
            logger.error(f"[HOSTING] Error al subir imagen: {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"[HOSTING] Excepción en upload_image: {e}")
        return None


def upload_image_from_url(
    image_url: str, alt_text: Optional[str] = None, credit: Optional[str] = None
) -> Optional[int]:
    try:
        resp = requests.get(
            image_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30
        )
        resp.raise_for_status()
        files = {"file": ("image.jpg", BytesIO(resp.content))}
        logger.info(f"[HOSTING] Subiendo imagen desde URL: {image_url}")
        headers = get_headers()
        headers.pop("Content-Type", None)
        r = requests.post(rest_url("media"), headers=headers, files=files, timeout=30)
        if r.status_code in (200, 201):
            media_id = r.json().get("id")
            if media_id and (alt_text or credit):
                try:
                    meta_payload = {}
                    if alt_text:
                        meta_payload["alt_text"] = alt_text
                    if credit:
                        meta_payload["caption"] = credit
                        meta_payload["description"] = credit
                    requests.post(
                        rest_url(f"media/{media_id}"),
                        headers=get_headers(),
                        json=meta_payload,
                        timeout=15,
                    )
                except Exception as e:
                    logger.warning(f"[HOSTING] No se pudo asignar créditos: {e}")
            return int(media_id)
        else:
            logger.error(f"[HOSTING] Error al subir imagen: {r.status_code}")
            return None
    except Exception as e:
        logger.error(f"[HOSTING] Error subiendo imagen: {e}")
        return None


def upload_audio(audio_path: str) -> Optional[int]:
    """Sube un archivo de audio a WordPress. Solo acepta MP3."""
    try:
        # Validar extensión: solo MP3 permitido
        ext = Path(audio_path).suffix.lower()
        if ext == ".wav":
            logger.error(
                f"[HOSTING] ❌ Intento de subir archivo WAV ({audio_path}). No permitido. Convirtiendo a MP3..."
            )
            # Intentar conversión a MP3 como último recurso
            try:
                from src.shared.adapters.audio_converter import AudioConverter

                converter = AudioConverter()
                mp3_path = converter.convert_to_mp3(
                    input_path=audio_path,
                    bitrate="64k",
                    delete_original=False,
                )
                if mp3_path and Path(mp3_path).exists():
                    mp3_size = Path(mp3_path).stat().st_size / (1024 * 1024)
                    logger.info(
                        f"[HOSTING] ✅ WAV convertido a MP3: {mp3_path} ({mp3_size:.1f} MB)"
                    )
                    audio_path = mp3_path
                else:
                    logger.error(
                        "[HOSTING] ❌ Conversión WAV→MP3 falló. Audio NO subido."
                    )
                    return None
            except Exception as e:
                logger.error(f"[HOSTING] ❌ Error en conversión WAV→MP3: {e}")
                return None

        # Ahora seguro de que es MP3 (o conversión exitosa)
        headers = get_headers()
        headers.pop("Content-Type", None)
        file_size = Path(audio_path).stat().st_size
        logger.info(
            f"[HOSTING] Subiendo audio MP3: {audio_path} ({file_size / 1024 / 1024:.1f} MB)"
        )
        with open(audio_path, "rb") as f:
            files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
            resp = requests.post(
                rest_url("media"), headers=headers, files=files, timeout=30
            )
        if resp.status_code in (200, 201):
            media_id = resp.json().get("id")
            logger.info(f"[HOSTING] Audio subido, ID={media_id}")
            return int(media_id)
        else:
            logger.error(
                f"[HOSTING] Error al subir audio: {resp.status_code} {resp.text}"
            )
            return None
    except Exception as e:
        logger.error(f"[HOSTING] Excepción en upload_audio: {e}")
        return None


def ensure_category(name: str) -> Optional[int]:
    try:
        r = requests.get(
            rest_url("categories"),
            headers=get_headers(),
            params={"search": name},
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                return data[0]["id"]
        r = requests.post(
            rest_url("categories"),
            headers=get_headers(),
            json={"name": name},
            timeout=30,
        )
        if r.status_code in (200, 201):
            return r.json().get("id")
        else:
            logger.warning(f"[HOSTING] No se pudo crear categoría: {r.status_code}")
    except Exception as e:
        logger.warning(f"[HOSTING] Error con categoría: {e}")
    return None


def ensure_tag(name: str) -> Optional[int]:
    try:
        r = requests.get(
            rest_url("tags"), headers=get_headers(), params={"search": name}, timeout=30
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                tag_id = data[0]["id"]
                logger.info(f"[HOSTING] Tag reutilizado: '{name}' → ID={tag_id}")
                return tag_id
        r = requests.post(
            rest_url("tags"), headers=get_headers(), json={"name": name}, timeout=30
        )
        if r.status_code in (200, 201):
            tag_id = r.json().get("id")
            logger.info(f"[HOSTING] Tag creado: '{name}' → ID={tag_id}")
            return tag_id
        else:
            logger.warning(f"[HOSTING] No se pudo crear tag: {r.status_code}")
    except Exception as e:
        logger.warning(f"[HOSTING] Error con tag: {e}")
    return None


def publish_post(
    title: str,
    content: str,
    categories: Optional[List] = None,
    tags: Optional[List] = None,
    is_draft: bool = False,
    featured_image: Optional[int] = None,
    excerpt: Optional[str] = None,
    slug: Optional[str] = None,
    seo_title: Optional[str] = None,
    focus_keyword: Optional[str] = None,
    canonical_url: Optional[str] = None,
) -> Optional[str]:
    try:
        headers = get_headers()
        payload = {
            "title": seo_title or title,
            "content": content,
            "status": "draft" if is_draft else "publish",
            "categories": categories or [],
        }

        meta_fields = {}
        meta_fields["_yoast_wpseo_focuskw"] = focus_keyword or title
        if excerpt:
            payload["excerpt"] = excerpt
            meta_fields["_yoast_wpseo_metadesc"] = excerpt
        if seo_title:
            meta_fields["_yoast_wpseo_title"] = seo_title
        if canonical_url:
            meta_fields["_yoast_wpseo_canonical"] = canonical_url
        meta_fields["_yoast_wpseo_opengraph-title"] = seo_title or title
        meta_fields["_yoast_wpseo_opengraph-description"] = excerpt or ""
        if featured_image:
            meta_fields["_yoast_wpseo_opengraph-image"] = str(featured_image)
            meta_fields["_yoast_wpseo_twitter-image"] = str(featured_image)
        meta_fields["_yoast_wpseo_twitter-title"] = seo_title or title
        meta_fields["_yoast_wpseo_twitter-description"] = excerpt or ""

        if meta_fields:
            payload["meta"] = meta_fields

        if slug:
            payload["slug"] = slug
        if tags:
            payload["tags"] = tags
        if featured_image:
            payload["featured_media"] = int(featured_image)

        logger.info(f"[HOSTING] Publicando: {title}")
        resp = requests.post(
            rest_url("posts"), headers=headers, json=payload, timeout=30
        )

        if resp.status_code in (200, 201):
            post_url = resp.json().get("link")
            if post_url and "api.nbes.blog" in post_url:
                post_url = post_url.replace("api.nbes.blog", "nbes.blog")
            logger.info(f"[HOSTING] ✅Publicado: {post_url}")
            return post_url
        else:
            logger.error(f"[HOSTING] Error: {resp.status_code} {resp.text}")
            return None
    except Exception as e:
        logger.error(f"[HOSTING] Excepción: {e}")
        return None


class WordPressPublisher:
    """Publisher para WordPress Hosting."""

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
            logger.error(f"[HOSTING] Error cargando artículos: {e}")
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
            logger.error(f"[HOSTING] Error cargando posts: {e}")
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
            logger.error(f"[HOSTING] Error guardando post: {e}")
            return False

    def publish_articles(
        self, articles: Optional[List[Dict]] = None, posts: Optional[List[Dict]] = None
    ) -> Dict:
        """Publica artículos en WordPress."""
        if articles is None:
            articles = self._load_articles_from_mongo()
        if posts is None:
            posts = self._load_posts_from_mongo()

        if not articles:
            logger.warning("[HOSTING] No hay artículos para publicar")
            return {"status": "warning", "message": "No hay artículos"}

        if not posts:
            logger.warning("[HOSTING] No hay posts para publicar")
            return {"status": "warning", "message": "No hay posts"}

        logger.info(f"[HOSTING] Publicando {len(articles)} artículos")

        published = 0
        errors = 0

        for idx, art in enumerate(articles):
            title = (
                art.get("title")
                or (
                    posts[idx].get("title_es")
                    if idx < len(posts) and isinstance(posts[idx], dict)
                    else None
                )
                or art.get("title_es")
                or (
                    posts[idx].get("tweet")
                    if idx < len(posts) and isinstance(posts[idx], dict)
                    else None
                )
            )

            if not title or not art.get("content"):
                logger.warning(f"[HOSTING] Artículo inválido idx={idx}")
                continue

            if idx < len(posts) and posts[idx].get("wp_url"):
                logger.warning(f"[HOSTING] Ya publicado: {title}")
                continue

            labels = art.get("labels", [])
            categoria = labels[0] if labels else "Noticias"

            if categoria in ["Video", "Política", "Política internacional"]:
                categoria = "Noticias"

            categoria_id = ensure_category(categoria)

            precomputed_tags = (
                posts[idx].get("hashtags", [])
                if idx < len(posts) and isinstance(posts[idx], dict)
                else []
            )
            all_tags = list(set((labels or art.get("tags", [])) + precomputed_tags))
            tag_ids = [ensure_tag(t) for t in all_tags if isinstance(t, str)]
            tag_ids = [tid for tid in tag_ids if tid is not None]

            is_draft = art.get("is_draft", False)
            excerpt = art.get("excerpt")

            image_path = art.get("image_path")
            image_url = art.get("image_url")
            alt_text = art.get("alt_text")
            image_credit = art.get("image_credit")

            featured_image = None
            if image_path and Path(image_path).exists():
                featured_image = upload_image(
                    image_path, credit=image_credit, alt_text=alt_text
                )
            elif image_url:
                featured_image = upload_image_from_url(
                    image_url, alt_text=alt_text, credit=image_credit
                )

            # === TTS Audio Upload ===
            audio_path = art.get("tts_audio_path")
            audio_block = ""
            if audio_path and Path(audio_path).exists():
                audio_id = upload_audio(audio_path)
                if audio_id:
                    # Obtener URL del audio desde WordPress
                    try:
                        media_resp = requests.get(
                            rest_url(f"media/{audio_id}"),
                            headers=get_headers(),
                            timeout=15,
                        )
                        if media_resp.status_code == 200:
                            audio_url = media_resp.json().get("source_url", "")
                            # Crear bloque Gutenberg para audio
                            audio_block = f"""
<!-- wp:audio {{"id": {audio_id}}} -->
<audio controls src="{audio_url}" controlsList="nodownload" oncontextmenu="return false"></audio>
<!-- /wp:audio -->
"""
                            logger.info(
                                f"[HOSTING] Audio bloque preparado (ID={audio_id})"
                            )
                    except Exception as e:
                        logger.warning(
                            f"[HOSTING] No se pudo obtener URL del audio: {e}"
                        )

            # === Prepare content with audio block ===
            article_content = art.get("content", "")
            if audio_block:
                article_content = audio_block + "\n\n" + article_content

            post_url = publish_post(
                title=title,
                content=article_content,
                categories=[categoria_id] if categoria_id else None,
                tags=tag_ids,
                is_draft=is_draft,
                excerpt=excerpt,
                featured_image=featured_image,
                slug=art.get("slug"),
                seo_title=art.get("seo_title"),
                focus_keyword=art.get("focus_keyword"),
                canonical_url=art.get("canonical_url"),
            )

            if post_url:
                logger.info(f"[HOSTING] ✅Publicado: {post_url}")
                if idx < len(posts) and isinstance(posts[idx], dict):
                    posts[idx]["wp_url"] = post_url
                    self._save_post(posts[idx])
                published += 1
            else:
                logger.error(f"[HOSTING] Error al publicar: {title}")
                errors += 1

        return {
            "status": "success",
            "published": published,
            "errors": errors,
            "total": len(articles),
        }


def run() -> Dict:
    """Función principal."""
    publisher = WordPressPublisher()
    return publisher.publish_articles()


if __name__ == "__main__":
    result = run()
    print(f"[HOSTING] Resultado: {result}")
