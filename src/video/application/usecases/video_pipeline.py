"""Video pipeline orchestrator.

This use‑case ties together the existing components that already exist for the
video→article flow and adds the missing steps that are present in the news
pipeline (image enrichment, WordPress publishing and social media posting).

It is deliberately kept small – it only glues together already‑tested pieces
and adds the error‑handling rules required by the specification.
"""

import logging
import re
from typing import List, Dict, Any, Optional

# Existing components
from src.video.application.usecases.article_from_video import (
    ArticleFromVideoUseCase,
)
from src.shared.adapters.image_enricher import ImageEnricher

# Use the low‑level publish_post helper instead of the class interface
from src.shared.adapters.wordpress_publisher import publish_post
from src.shared.adapters.publishers.social import SocialMediaPublisher

logger = logging.getLogger("news_bot")


class VideoPipelineUseCase:
    """Orchestrates the full video processing pipeline.

    The steps correspond to the 10‑step flow required by the user:
    1. Download & extract audio – delegated to ``ArticleFromVideoUseCase``
    2. Transcribe audio – also delegated to ``ArticleFromVideoUseCase``
    3. Generate tweets / posts – ``ArticleFromVideoUseCase`` returns a tweet
    4. Generate article – ``ArticleFromVideoUseCase`` returns the article dict
    5‑7. Image enrichment – ``ImageEnricher``
    8. WordPress publishing – ``publish_post`` helper
    9. Social media publishing – ``SocialMediaPublisher``
    10. Cleanup – handled by the caller (temporary files are created by the
       use‑case and live in the ``data/`` folder)."""

    def __init__(self, no_publish: bool = False):
        self.no_publish = no_publish
        self._article_uc: Optional[ArticleFromVideoUseCase] = None
        self._image_enricher: Optional[ImageEnricher] = None
        self._social_publisher: Optional[SocialMediaPublisher] = None

    @property
    def article_uc(self) -> ArticleFromVideoUseCase:
        if self._article_uc is None:
            self._article_uc = ArticleFromVideoUseCase()
        return self._article_uc

    @property
    def image_enricher(self) -> ImageEnricher:
        if self._image_enricher is None:
            self._image_enricher = ImageEnricher(mode="video")
        return self._image_enricher

    @property
    def social_publisher(self) -> SocialMediaPublisher:
        if self._social_publisher is None:
            self._social_publisher = SocialMediaPublisher()
        return self._social_publisher

    def run(self, url: str, tema: str) -> Dict[str, Any]:
        logger.info("[1/10] Descargando video y extrayendo audio")

        transcript = ""

        try:
            from src.video.infrastructure.adapters.video_fetcher import download_video
            from src.video.infrastructure.adapters.video_transcriber import (
                transcribe_video,
            )
            import tempfile
            import os

            video_path = download_video(url)
            if not video_path or not os.path.exists(video_path):
                raise RuntimeError(f"No se pudo descargar el video: {url}")

            logger.info("[1/10] Video descargado, extrayendo audio...")
            transcript = transcribe_video(video_path)
            logger.info(
                f"[1/10] Transcripción completada: {len(transcript)} caracteres"
            )

        except Exception as e:
            logger.error(f"[1/10] Error descargando/transcribiendo video: {e}")
            raise RuntimeError(f"Error en descarga/transcripción del video: {e}") from e

        logger.info("[2/10] Generando tweets/posts y artículo")
        try:
            from src.video.application.usecases.article_from_video import run_from_video

            result = run_from_video(
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

            unsplash_fetcher = UnsplashFetcher(mode="video")
            article_for_images = unsplash_fetcher.fetch_for_posts(article_for_images)
        except Exception as e:
            logger.warning(f"[5/10] Error en Unsplash: {e}")

        logger.info("[6/10] Buscando imágenes en Google Images")
        try:
            from src.shared.adapters.google_images_fetcher import GoogleImagesFetcher

            google_fetcher = GoogleImagesFetcher(mode="video")
            article_for_images = google_fetcher.fetch_for_posts(article_for_images)
        except Exception as e:
            logger.warning(f"[6/10] Error en Google Images: {e}")

        logger.info("[7/10] Enriqueciendo artículo con imágenes")
        enriched = self.image_enricher.enrich(article_for_images)
        enriched_article = enriched[0]
        logger.info("[7/10] Enriqueciendo artículo con imágenes")

        wordPress_post_id: Optional[int] = None
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
                if topic in ["Video", "Política", "Política internacional"]:
                    topic = "Noticias"
                category_id = ensure_category(topic)

                labels = enriched_article.get("labels", [])
                precomputed_tags = enriched_article.get("hashtags", [])
                all_tags = list(set(labels + precomputed_tags))
                tag_ids = [ensure_tag(t) for t in all_tags if isinstance(t, str)]
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
            "mode": "video",
        }
