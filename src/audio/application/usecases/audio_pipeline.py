"""Audio pipeline orchestrator.

This use-case orchestrates the complete audio-to-article processing pipeline.
"""

import time
from typing import Dict, Any, List, Optional

from src.logging_config import get_logger

logger = get_logger("audio_bot.usecase")

from src.audio.application.usecases.article_from_audio import run_from_audio
from src.shared.application.usecases.base_pipeline import BasePipelineUseCase


class AudioPipelineUseCase(BasePipelineUseCase):
    """Orchestrates complete audio processing pipeline."""

    def __init__(self, no_publish: bool = False):
        super().__init__(mode="audio", no_publish=no_publish)

    def run(self, url: str, tema: str) -> Dict[str, Any]:
        from src.audio.infrastructure.adapters.audio_fetcher import (
            download_audio,
            has_audio_stream,
        )
        from src.audio.infrastructure.adapters.audio_transcriber import transcribe_audio

        step_start = time.time()
        logger.info("[1/4] Descargando audio y transcribiendo...")

        transcript = ""
        audio_path: Optional[str] = None

        try:
            audio_path = download_audio(url)
            if not audio_path or not has_audio_stream(audio_path):
                raise RuntimeError(f"Audio without valid stream: {url}")

            self._track_temp_file(audio_path)
            transcript = transcribe_audio(audio_path)
            logger.info(
                f"[1/4] Audio descargado y transcrito ({len(transcript)} caracteres) en {time.time() - step_start:.1f}s"
            )

        except Exception as e:
            logger.error(f"[1/4] Error en descarga/transcripción: {e}")
            raise RuntimeError(f"Error in audio download/transcription: {e}") from e

        # Steps 2-4: Article generation
        step_start = time.time()
        logger.info("[2/4] Generando artículo y posts con IA...")
        try:
            result = run_from_audio(
                transcript=transcript, url=url, tema=tema, llm_provider="openrouter"
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
