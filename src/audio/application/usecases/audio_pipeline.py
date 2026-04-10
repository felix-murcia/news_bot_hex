"""Audio pipeline orchestrator.

Este use-case orquesta el procesamiento completo de audio a artículo publicado.
"""

import logging
import re
from typing import Dict, Any, Optional

from src.audio.infrastructure.adapters.audio_fetcher import (
    download_audio,
    has_audio_stream,
)
from src.audio.infrastructure.adapters.audio_transcriber import transcribe_audio
from src.audio.application.usecases.article_from_audio import run_from_audio
from src.shared.adapters.image_enricher import ImageEnricher

from src.shared.adapters.wordpress_publisher import publish_post
from src.shared.adapters.publishers.social import SocialMediaPublisher

logger = logging.getLogger("audio_bot")


class AudioPipelineUseCase:
    """Orquesta el procesamiento completo de audio."""

    def __init__(self, no_publish: bool = False):
        self.no_publish = no_publish
        self._image_enricher: Optional[ImageEnricher] = None
        self._social_publisher: Optional[SocialMediaPublisher] = None

    @property
    def image_enricher(self) -> ImageEnricher:
        if self._image_enricher is None:
            self._image_enricher = ImageEnricher(mode="audio")
        return self._image_enricher

    @property
    def social_publisher(self) -> SocialMediaPublisher:
        if self._social_publisher is None:
            self._social_publisher = SocialMediaPublisher()
        return self._social_publisher

    def run(self, url: str, tema: str) -> Dict[str, Any]:
        logger.info("[1/10] Descargando audio")

        transcript = ""

        try:
            audio_path = download_audio(url)
            if not audio_path or not has_audio_stream(audio_path):
                raise RuntimeError(f"Audio sin flujo de audio válido: {url}")

            logger.info("[1/10] Audio descargado, transcribiendo...")
            transcript = transcribe_audio(audio_path)
            logger.info(
                f"[1/10] Transcripción completada: {len(transcript)} caracteres"
            )

        except Exception as e:
            logger.error(f"[1/10] Error descargando/transcribiendo audio: {e}")
            raise RuntimeError(f"Error en descarga/transcripción del audio: {e}") from e

        logger.info("[2/10] Generando tweets/posts y artículo")
        try:
            result = run_from_audio(
                transcript=transcript, url=url, tema=tema, llm_provider="openrouter"
            )
        except Exception as e:
            logger.error(f"[2/10] Error en generación de contenido: {e}")
            raise

        article = result["article"]
        tweet = result["tweet"]

        logger.info("[3/10] Generando tweets/posts")
        tweets = [tweet]

        logger.info("[4/10] Generando artículo profesional en español")
        article_data = article
        article_for_images = [article_data]

        logger.info("[5/10] Buscando imágenes en Unsplash")
        try:
            from src.shared.adapters.unsplash_fetcher import UnsplashFetcher

            unsplash_fetcher = UnsplashFetcher(mode="audio")
            article_for_images = unsplash_fetcher.fetch_for_posts(article_for_images)
        except Exception as e:
            logger.warning(f"[5/10] Error en Unsplash: {e}")

        logger.info("[6/10] Buscando imágenes en Google Images")
        try:
            from src.shared.adapters.google_images_fetcher import GoogleImagesFetcher

            google_fetcher = GoogleImagesFetcher(mode="audio")
            article_for_images = google_fetcher.fetch_for_posts(article_for_images)
        except Exception as e:
            logger.warning(f"[6/10] Error en Google Images: {e}")

        logger.info("[7/10] Enriqueciendo artículo con imágenes")
        enriched = self.image_enricher.enrich(article_for_images)
        enriched_article = enriched[0]

        wordpress_post_id = None
        if not self.no_publish:
            logger.info("[8/10] Publicando en WordPress")
            try:
                from src.shared.adapters.wordpress_publisher import (
                    ensure_category,
                    ensure_tag,
                )

                topic = (
                    enriched_article.get("labels", [tema])[0]
                    if enriched_article.get("labels")
                    else tema
                )
                if topic in ["Audio", "Podcast"]:
                    topic = "Noticias"
                category_id = ensure_category(topic)

                labels = enriched_article.get("labels", [])
                tag_ids = [ensure_tag(t) for t in labels if isinstance(t, str)]
                tag_ids = [tid for tid in tag_ids if tid is not None]

                image_url = enriched_article.get("image_url")
                featured_image_id = None
                if image_url and "nbes.blog" not in image_url:
                    from src.shared.adapters.wordpress_publisher import (
                        upload_image_from_url,
                    )

                    try:
                        featured_image_id = upload_image_from_url(
                            image_url,
                            alt_text=enriched_article.get("alt_text"),
                            credit=enriched_article.get("image_credit"),
                        )
                    except Exception as e:
                        logger.warning(f"[WORDPRESS] Error subiendo imagen: {e}")

                content = enriched_article.get("content", "")
                content = re.sub(
                    r"<h1[^>]*>.*?</h1>", "", content, flags=re.DOTALL | re.IGNORECASE
                )
                content = content.strip()

                wordpress_post_id = publish_post(
                    title=enriched_article.get("title"),
                    content=content,
                    categories=[category_id] if category_id else None,
                    tags=tag_ids if tag_ids else None,
                    is_draft=False,
                    featured_image=featured_image_id,
                    excerpt=enriched_article.get("excerpt"),
                    slug=enriched_article.get("slug"),
                    seo_title=None,
                    focus_keyword=enriched_article.get("title"),
                    canonical_url=None,
                )
            except Exception as e:
                logger.warning(f"[8/10] Fallo en publicación de WordPress: {e}")
                wordpress_post_id = None

        if wordpress_post_id and enriched_article.get("url"):
            wp_url = enriched_article["url"]
            enriched_article["wp_url"] = wp_url
        else:
            logger.info("[8/10] Publicación en WordPress omitida por --no-publish")

        logger.info("[9/10] Publicando en redes sociales")
        try:
            post_for_social = {
                "tweet": tweets[0] if tweets else "",
                "wp_url": enriched_article.get(
                    "wp_url", enriched_article.get("url", "")
                ),
                "url": url,
                "image_url": enriched_article.get("image_url", ""),
            }
            social_results = self.social_publisher.publish(post_for_social)
        except Exception as e:
            logger.error(f"[9/10] Error al publicar en redes sociales: {e}")
            social_results = []

        logger.info("[10/10] Limpieza de archivos temporales")
        logger.info("[10/10] Limpieza completada")

        return {
            "url": url,
            "transcript": transcript,
            "article": article_data,
            "article_file": result.get("article_file", ""),
            "images": enriched_article.get("image_url", []),
            "tweets": tweets,
            "wordpress_post_id": wordpress_post_id,
            "social_results": social_results,
            "mode": "audio",
        }
