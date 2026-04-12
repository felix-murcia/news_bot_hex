"""Video pipeline orchestrator.

This use-case orchestrates the complete video-to-article processing pipeline
by coordinating download, transcription, article generation, image enrichment,
and publishing to WordPress and social media.
"""

import os
import time
from typing import Dict, Any, List, Optional

from config.settings import Settings
from src.logging_config import get_logger

logger = get_logger("video_bot.usecase")

from src.video.application.usecases.article_from_video import (
    run_from_video,
)
from src.shared.application.usecases.base_pipeline import BasePipelineUseCase


class VideoPipelineUseCase(BasePipelineUseCase):
    """Orchestrates the complete video processing pipeline."""

    def __init__(self, no_publish: bool = False):
        super().__init__(mode="video", no_publish=no_publish)

    def run(self, url: str, tema: str) -> Dict[str, Any]:
        step_start = time.time()
        logger.info("[1/4] Descargando video y extrayendo audio...")

        transcript = ""
        video_path: Optional[str] = None

        try:
            from src.video.infrastructure.adapters.video_fetcher import download_video
            from src.video.infrastructure.adapters.video_transcriber import (
                transcribe_video,
            )

            video_path = download_video(url)
            if not video_path or not os.path.exists(video_path):
                raise RuntimeError(f"Failed to download video: {url}")

            self._track_temp_file(video_path)
            transcript = transcribe_video(video_path)
            logger.info(
                f"[1/4] Video descargado y transcrito ({len(transcript)} caracteres) en {time.time() - step_start:.1f}s"
            )

        except Exception as e:
            logger.error(f"[1/4] Error en descarga/transcripción de video: {e}")
            raise RuntimeError(f"Error in video download/transcription: {e}") from e

        # Steps 2-4: Article generation
        step_start = time.time()
        logger.info("[2/4] Generando artículo y posts con IA...")
        try:
            result = run_from_video(
                transcript=transcript, url=url, tema=tema, llm_provider=Settings.AI_PROVIDER
            )
            logger.info(f"[2/4] Artículo generado en {time.time() - step_start:.1f}s")
        except Exception as e:
            logger.error(f"[2/4] Error en generación de contenido: {e}")
            raise

        article = result["article"]
        tweet = result["tweet"]
        tweets: List[str] = [tweet]

        # Steps 5-7: Image enrichment
        step_start = time.time()
        logger.info("[3/7] Enriqueciendo con imágenes (Unsplash + Google)...")
        articles_for_images = [article]
        enriched_articles = self._enrich_with_images(articles_for_images)
        enriched_article = enriched_articles[0]
        logger.info(f"[3/7] Enriquecimiento completado en {time.time() - step_start:.1f}s")

        # Step 8: WordPress
        step_start = time.time()
        wordpress_url: Optional[str] = None
        if not self.no_publish:
            logger.info("[4/8] Publicando en WordPress...")
            wordpress_url = self._publish_to_wordpress(enriched_article, tema)
            if wordpress_url:
                enriched_article["wp_url"] = wordpress_url
                logger.info(f"[4/8] Publicado en WordPress en {time.time() - step_start:.1f}s: {wordpress_url}")
            else:
                logger.warning(f"[4/8] No se obtuvo URL de WordPress")
        else:
            logger.info("[4/8] WordPress omitido (no-publish mode)")

        # Step 9: Social media
        step_start = time.time()
        logger.info("[5/9] Publicando en redes sociales...")
        social_results = self._publish_to_social(enriched_article, tweet, url)
        logger.info(f"[5/9] Redes sociales procesadas en {time.time() - step_start:.1f}s")

        # Step 10: Cleanup
        logger.info("[6/10] Limpiando archivos temporales...")
        self._cleanup_temp_files()

        return self.build_result(
            url=url,
            transcript=transcript,
            article=enriched_article,
            article_file=result.get("article_file", ""),
            tweets=tweets,
            wordpress_url=wordpress_url,
            social_results=social_results,
        )
