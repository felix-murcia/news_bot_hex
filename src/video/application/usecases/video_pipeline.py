"""Video pipeline orchestrator.

This use-case orchestrates the complete video-to-article processing pipeline
by coordinating download, transcription, article generation, image enrichment,
and publishing to WordPress and social media.
"""

import os
import time
import random
from typing import Dict, Any, List, Optional

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("video_bot.usecase")

from src.shared.application.usecases.article_from_transcript import run_from_transcript
from src.shared.application.usecases.base_pipeline import BasePipelineUseCase
from src.shared.domain.ports.video_generator_port import VideoGeneratorPort
from src.shared.domain.ports.video_generator_port import VideoGeneratorPort


class VideoPipelineUseCase(BasePipelineUseCase):
    """Orchestrates the complete video processing pipeline."""

    def __init__(
        self,
        no_publish: bool = False,
        video_generator: Optional[VideoGeneratorPort] = None,
    ):
        """
        Inicializa el pipeline de video.

        Args:
            no_publish: Si True, omite publicación en WordPress y redes.
            video_generator: Adaptador para generar videos (inyección de dependencia).
                           Si None, se usa la instancia global por defecto.
        """
        super().__init__(mode="video", no_publish=no_publish)
        self.video_generator = video_generator or self._create_video_generator()

    @staticmethod
    def _create_video_generator() -> VideoGeneratorPort:
        """
        Crea una instancia del generador de videos por defecto.

        Returns:
            Instancia del adaptador de generación de video.
        """
        from src.shared.adapters.video_generator import get_video_generator

        return get_video_generator()

    def run(self, url: str, tema: str) -> Dict[str, Any]:
        step_start = time.time()
        logger.info("[1/4] Descargando audio MP3 del video...")

        transcript = ""
        audio_path: Optional[str] = None

        try:
            from src.video.infrastructure.adapters.video_fetcher import download_mp3
            from src.video.infrastructure.adapters.video_transcriber import (
                transcribe_audio,
            )

            audio_path = download_mp3(url)
            if not audio_path or not os.path.exists(audio_path):
                raise RuntimeError(f"Failed to download audio MP3: {url}")

            self._track_temp_file(audio_path)
            transcript = transcribe_audio(audio_path)

            if len(transcript) < 200:
                logger.warning(
                    f"[1/4] Transcripción muy corta ({len(transcript)} chars). "
                    f"El artículo generado puede ser de baja calidad o impreciso."
                )

            logger.info(
                f"[1/4] Audio MP3 descargado y transcrito ({len(transcript)} caracteres) en {time.time() - step_start:.1f}s"
            )

        except Exception as e:
            logger.error(f"[1/4] Error en descarga/transcripción de audio: {e}")
            raise RuntimeError(f"Error in audio download/transcription: {e}") from e

        # Steps 2-4: Article generation
        step_start = time.time()
        logger.info("[2/4] Generando artículo y posts con IA...")
        try:
            result = run_from_transcript(
                transcript=transcript,
                url=url,
                tema=tema,
                llm_provider=Settings.AI_PROVIDER,
                source_type="video",
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
        logger.info(
            f"[3/7] Enriquecimiento completado en {time.time() - step_start:.1f}s"
        )

        # Step 4: Text-to-Speech
        step_start = time.time()
        logger.info("[4/8] Generando audio TTS del artículo...")
        try:
            from src.shared.adapters.tts_adapter import text_to_speech
            from src.shared.utils.text_cleaner import clean_text_for_tts

            article_text = enriched_article.get("content", "")
            if article_text:
                cleaned_text = clean_text_for_tts(article_text)
                tts_audio_path = text_to_speech(
                    text=cleaned_text,
                    voice=Settings.TTS_VOICE,
                    model=Settings.TTS_MODEL,
                )
                enriched_article["tts_audio_path"] = tts_audio_path
                logger.info(
                    f"[4/8] Audio TTS generado en {time.time() - step_start:.1f}s: {tts_audio_path}"
                )

                # Asegurar que el audio esté en MP3 (convertir si es WAV)
                from pathlib import Path
                from src.shared.adapters.audio_converter import AudioConverter

                _converter = AudioConverter()
                _audio_path = enriched_article.get("tts_audio_path")
                if _audio_path and Path(_audio_path).exists():
                    _ext = Path(_audio_path).suffix.lower()
                    if _ext == ".wav":
                        logger.info(
                            "[4/8] Convirtiendo WAV → MP3 (64k) para optimizar..."
                        )
                        try:
                            _mp3_path = _converter.convert_to_mp3(
                                input_path=_audio_path,
                                bitrate="64k",
                                delete_original=False,
                            )
                            if _mp3_path and Path(_mp3_path).exists():
                                enriched_article["tts_audio_path"] = _mp3_path
                                logger.info(
                                    f"[4/8] ✅ Audio ahora en MP3: {_mp3_path} ({Path(_mp3_path).stat().st_size / 1024 / 1024:.1f} MB)"
                                )
                            else:
                                logger.warning(
                                    "[4/8] ❌ Conversión WAV→MP3 falló. El audio seguirá siendo WAV y podría causar timeout."
                                )
                        except Exception as e:
                            logger.warning(f"[4/8] ❌ Error convirtiendo WAV→MP3: {e}")
            else:
                logger.warning("[4/8] No hay contenido para generar audio TTS")
        except Exception as e:
            logger.warning(f"[4/8] Error en generación TTS (no bloquea pipeline): {e}")

        # Step 5: Generación de video desde audio + imagen
        step_start = time.time()
        logger.info("[5/9] Generando video a partir del audio TTS...")
        try:
            tts_audio_path = enriched_article.get("tts_audio_path")
            if tts_audio_path and os.path.exists(tts_audio_path):
                video_path = self.video_generator.create_video_from_audio(
                    audio_path=tts_audio_path
                )
                if video_path:
                    enriched_article["generated_video_path"] = video_path
                    self._track_temp_file(video_path)
                    logger.info(
                        f"[5/9] Video generado en {time.time() - step_start:.1f}s: {video_path}"
                    )
                else:
                    logger.warning("[5/9] No se pudo generar el video")
            else:
                logger.warning(
                    "[5/9] No hay audio TTS disponible para generar video, saltando..."
                )
        except Exception as e:
            logger.warning(
                f"[5/9] Error en generación de video (no bloquea pipeline): {e}"
            )

        # Step 6: WordPress
        step_start = time.time()
        logger.info("[6/10] Publicando en WordPress...")
        wordpress_url: Optional[str] = None
        if not self.no_publish:
            logger.info("[6/10] Publicando en WordPress...")
            wordpress_url = self._publish_to_wordpress(enriched_article, tema)
            if wordpress_url:
                enriched_article["wp_url"] = wordpress_url
                logger.info(
                    f"[6/10]Publicado en WordPress en {time.time() - step_start:.1f}s: {wordpress_url}"
                )

                # Replace placeholder URL in tweet with actual WordPress URL
                if tweet and enriched_article.get("url"):
                    placeholder_url = enriched_article.get("url", "")
                    if placeholder_url in tweet:
                        tweet = tweet.replace(placeholder_url, wordpress_url)
                    elif "nbes.blog" in tweet:
                        # Replace any nbes.blog URL with the actual one
                        import re

                        tweet = re.sub(r"https?://nbes\.blog/\S+", wordpress_url, tweet)
                    # Append URL if not present
                    if wordpress_url not in tweet:
                        tweet = f"{tweet}\n\nMás info: {wordpress_url}"
                        from src.shared.utils.tweet_truncation import (
                            truncate_social_post,
                        )

                        tweet = truncate_social_post(tweet)
                    tweets = [tweet]  # Update tweets list with corrected tweet

                logger.info(f"[6/10] Tweet actualizado con URL de WordPress")
            else:
                logger.warning(
                    f"[6/10] No se obtuvo URL de WordPress — usando URL fallback"
                )
                # Fallback: use original video URL or placeholder article URL
                fallback_url = (
                    enriched_article.get("url")
                    or enriched_article.get("original_url")
                    or url
                )
                if fallback_url and fallback_url not in tweet:
                    tweet = f"{tweet}\n\nMás: {fallback_url}"
                    from src.shared.utils.tweet_truncation import truncate_social_post

                    tweet = truncate_social_post(tweet)
                    tweets = [tweet]
                    logger.info(f"[6/10] Tweet con URL fallback: {fallback_url}")
        else:
            logger.info("[6/10] WordPress omitido (no-publish mode)")

        # Step 7: Social media
        step_start = time.time()
        logger.info("[7/11] Publicando en redes sociales...")
        social_results = self._publish_to_social(enriched_article, tweet, url)
        logger.info(
            f"[7/11] Redes sociales procesadas en {time.time() - step_start:.1f}s"
        )

        # Step 8: Cleanup
        logger.info("[8/11] Limpiando archivos temporales...")
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
