"""Pipeline for processing a concrete URL.

Extracts content from the URL, inserts it as a VerifiedArticle, then runs
the exact same steps as the automatic pipeline (run_content → run_article →
images → audio → video → WordPress → social). No duplicate prompts or logic.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Optional

import logging
from src.news.application.usecases.metrics_collector import MetricsCollector
from src.news.domain.entities.processing_metric import PipelineType
from src.news.domain.ports import GeneratedArticlesRepository, GeneratedPostsRepository, VerifiedNewsRepository
from src.news.domain.ports.metrics_repository_port import MetricsRepositoryPort
from src.shared.domain.ports.video_generator_port import VideoGeneratorPort

logger = logging.getLogger(__name__)
class ProcessUrlPipeline:

    def __init__(
        self,
        content_extractor,
        generated_articles_repo: GeneratedArticlesRepository,
        generated_posts_repo: GeneratedPostsRepository,
        verified_news_repo: VerifiedNewsRepository,
        metrics_repo: Optional[MetricsRepositoryPort] = None,
        *,
        social_publisher,
        tts_usecase,
        wp_site_url: str = "",
        wp_default_image_url: str = "",
        image_unsplash_runner: Callable[[], None],
        image_google_runner: Callable[[], None],
        image_enricher_runner: Callable[[], None],
        wordpress_runner: Callable[[], None],
        video_generator_factory: Callable[[], VideoGeneratorPort],
        social_truncator: Callable[..., str],
        post_editor: Callable[..., str],
        cache_loader: Callable[..., tuple[Optional[str], str]],
        seo_helpers,
    ):
        self.content_extractor = content_extractor
        self.generated_articles_repo = generated_articles_repo
        self.generated_posts_repo = generated_posts_repo
        self._verified_news_repo = verified_news_repo
        self.metrics_repo = metrics_repo
        self._social_publisher = social_publisher
        self._tts_usecase = tts_usecase
        self._wp_site_url = wp_site_url
        self._wp_default_image_url = wp_default_image_url
        self._image_unsplash_runner = image_unsplash_runner
        self._image_google_runner = image_google_runner
        self._image_enricher_runner = image_enricher_runner
        self._wordpress_runner = wordpress_runner
        self._video_generator_factory = video_generator_factory
        self._social_truncator = social_truncator
        self._post_editor = post_editor
        self._cache_loader = cache_loader
        self._seo_helpers = seo_helpers

    def execute(self, url: str, job_id: Optional[str] = None) -> dict:
        logger.info(f"[PROCESS_URL] Starting pipeline for: {url}")

        metrics = None
        if self.metrics_repo and job_id:
            metrics = MetricsCollector(
                execution_id=job_id,
                pipeline_type=PipelineType.NEWS,
                metrics_repo=self.metrics_repo,
            )

        def run_step(name: str, fn, critical: bool = False):
            t = time.time_ns()
            try:
                fn()
                ms = (time.time_ns() - t) // 1_000_000
                if metrics:
                    metrics.record_step(name, "OK", ms)
                logger.info(f"[PROCESS_URL] ✅ {name} ({ms}ms)")
            except Exception as e:
                ms = (time.time_ns() - t) // 1_000_000
                if metrics:
                    metrics.record_step(name, "FAILED", ms, str(e))
                if critical:
                    raise
                logger.warning(f"[PROCESS_URL] ⚠️ {name} falló (no crítico): {e}")

        # ── Step 1: Extract content ─────────────────────────────────────────
        t = time.time_ns()
        content, _, titulo_fuente = self.content_extractor.extract(url)
        if not content or len(content) < 100:
            raise ValueError(f"No se pudo extraer contenido suficiente de: {url}")
        ms = (time.time_ns() - t) // 1_000_000
        if metrics:
            metrics.record_step("Extract Content", "OK", ms)
        logger.info(f"[PROCESS_URL] ✅ Extract Content ({len(content)} chars, {ms}ms)")

        # ── Step 2: Save as VerifiedArticle → verified_news ────────────────
        def save_verified():
            from src.news.domain.entities.verified_article import VerifiedArticle

            # Prioridad: 'Title:' de Jina (metadato de la página) > primera
            # línea del cuerpo > la URL. En páginas con banner de cookies la
            # primera línea era el banner ("Continue without agreeing →").
            titulo = titulo_fuente or next(
                (l.strip() for l in content.splitlines() if l.strip()), url
            )
            if titulo.startswith("#"):
                titulo = titulo.lstrip("#").strip()
            title = titulo[:200]

            # title_es vacío a propósito: el LLM genera el título en español
            # como <h1> del artículo (paso "Generate Articles") y article.py lo
            # extrae y lo escribe de vuelta en el post. No se traduce por API
            # de Google (ver src/shared/adapters/translator.py).
            title_es = ""

            article = VerifiedArticle(
                title=title,
                desc=content[:500],
                source="web",
                origin="URL directa",
                url=url,
                publishedAt=datetime.now(),
                tema="Noticias",
                resumen=content[:500],
                score=10,
                model_prediction="real",
                confidence=0.95,
                verification={"verified": True},
                content=content,
                original_url=url,
                title_es=title_es,
                source_url=url,
            )

            self._verified_news_repo.delete_all_news()
            self._verified_news_repo.insert_news([article])

        run_step("Save Verified Article", save_verified, critical=True)

        # ── Step 3: Generate Posts (same as automatic pipeline) ─────────────
        def generate_posts():
            from src.news.application.usecases.content import run_content
            posts = run_content(
                use_gemini=True,
                mode="news",
                generated_posts_repo=self.generated_posts_repo,
                verified_news_repo=self._verified_news_repo,
                social_truncator=self._social_truncator,
                post_editor=self._post_editor,
                cache_loader=self._cache_loader,
            )
            # Fail-fast: run_content omite por-item las noticias cuya IA se
            # negó (baja calidad). En el pipeline automático eso es legítimo
            # (N artículos RSS), pero aquí hay UNA sola url: 0 posts = nada
            # que publicar, y el pipeline termina sin quemar recursos en
            # imágenes, audio, vídeo y publicación.
            if not posts:
                raise RuntimeError(
                    f"No se generó ningún post para {url}: la IA descartó el "
                    "contenido por insuficiente o de baja calidad. No hay nada "
                    "que publicar: el pipeline termina aquí."
                )

        run_step("Generate Posts", generate_posts, critical=True)

        # ── Steps 4-5: Generate Articles ‖ Fetch Images (parallel) ─────────
        # F4: Generate Articles (writes generated_articles) and Fetch Images
        # (reads/writes generated_posts) are independent: Fetch Images does NOT
        # read generated_articles. Run them in parallel and join before
        # Enrich Images. Both are critical: exceptions propagate via .result().
        def generate_articles():
            from src.news.application.usecases.article import run as run_article

            generated = run_article(
                use_gemini=True,
                wp_site_url=self._wp_site_url,
                wp_default_image_url=self._wp_default_image_url,
                generated_articles_repo=self.generated_articles_repo,
                generated_posts_repo=self.generated_posts_repo,
                verified_news_repo=self._verified_news_repo,
                seo_helpers=self._seo_helpers,
            )
            # Fail-fast: si no se generó artículo para la url (p. ej. el post
            # no coincide con la URL verificada, o el LLM no devolvió cuerpo),
            # no hay nada que leer en audio/vídeo/publicación. Termina aquí.
            if not generated:
                raise RuntimeError(
                    f"No se generó artículo para {url}: no hay contenido que "
                    "publicar: el pipeline termina aquí."
                )

        def fetch_images():
            self._image_unsplash_runner()
            self._image_google_runner()

        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_articles = executor.submit(run_step, "Generate Articles", generate_articles, True)
            fut_images = executor.submit(run_step, "Fetch Images", fetch_images, True)
            # Join: wait for both. Articles first to preserve the original
            # priority (if both fail, the articles error is the one raised).
            fut_articles.result()
            fut_images.result()

        # ── Step 6: Enrich Images ───────────────────────────────────────────
        def enrich_images():
            self._image_enricher_runner()

        run_step("Enrich Images", enrich_images, critical=True)

        # ── F12: read generated_articles ONCE (stable after enrich) ────────
        # Reused by Generate Audio, Generate Video and the final read, instead
        # of re-querying MongoDB at each step.
        articles_list = [
            a for a in self.generated_articles_repo.load_all()
            if a.get("original_url") == url
        ]

        # ── Step 7: Generate Audio ──────────────────────────────────────────
        def generate_audio():
            if articles_list:
                updated = self._tts_usecase.execute_batch(articles_list)
                for article in updated:
                    if article.get("tts_audio_path"):
                        article_id = article.get("_id")
                        if article_id:
                            self.generated_articles_repo.update_tts_audio_path(str(article_id), article["tts_audio_path"])

        run_step("Generate Audio", generate_audio, critical=True)

        # ── Step 8: Generate Video ──────────────────────────────────────────
        def generate_video():
            video_gen = self._video_generator_factory()
            if video_gen.is_available():
                for article in articles_list:
                    audio_path = article.get("tts_audio_path")
                    if audio_path and os.path.exists(audio_path):
                        video_path = video_gen.create_video_from_audio(
                            audio_path=audio_path,
                            image=article.get("image_url"),
                        )
                        if video_path:
                            article_id = article.get("_id")
                            if article_id:
                                self.generated_articles_repo.update_generated_video_path(str(article_id), video_path)
                            # F3: propagate video_path to generated_posts so
                            # Facebook (which reads post["video_path"]) can
                            # publish the video in the URL/API flow.
                            original_url = article.get("original_url")
                            if original_url:
                                # Update the post with video_path
                                posts = self.generated_posts_repo.load_all()
                                for post in posts:
                                    if post.get("url") == original_url:
                                        post["video_path"] = video_path
                                        break
                                self.generated_posts_repo.save_all(posts)

        run_step("Generate Video", generate_video, critical=True)

        # ── Step 9: Publish WordPress ───────────────────────────────────────
        def publish_wordpress():
            self._wordpress_runner()

        run_step("Publish WordPress", publish_wordpress, critical=True)

        # ── Step 10: Publish Social ─────────────────────────────────────────
        def publish_social():
            try:
                self._social_publisher.publish_all()
            except Exception as e:
                logger.error(f"[PROCESS_URL] Social publisher error: {e}")
                raise RuntimeError(f"Social publisher crítico falló: {e}")

        run_step("Publish Social", publish_social, critical=True)

        if metrics:
            try:
                metrics.flush()
            except Exception as e:
                logger.warning(f"[PROCESS_URL] Could not flush metrics: {e}")

        # Return compatible dict for ProcessUrlJobCoordinator
        # F12: reuse articles_list (already enriched with tts_audio_path and
        # generated_video_path by the steps above) instead of re-reading.
        article = dict(articles_list[0]) if articles_list else {}
        article.pop("_id", None)
        posts = self.generated_posts_repo.load_all()
        post = posts[0] if posts else {}

        logger.info("[PROCESS_URL] ✅ Pipeline completed")
        return {
            "article_data": {"article": article},
            "post": post.get("tweet", ""),
            "mode": "gemini",
            "publish_results": [],
        }
