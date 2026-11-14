import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.news.domain.ports import ContentExtractor, GeneratedArticlesRepository, GeneratedPostsRepository
import logging
from src.shared.domain.ports.video_generator_port import VideoGeneratorPort
from src.shared.domain.services.ai_providers import AiProviders
from src.news.application.usecases.article_from_news import ArticleFromNewsUseCase

logger = logging.getLogger(__name__)
def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def check_copyright(url: str, domains: Optional[list[str]] = None) -> bool:
    """Check copyright risk for a URL."""
    url_lower = url.lower()
    return any(domain.lower() in url_lower for domain in (domains or []))


class NewsToNewsUseCase:
    """Caso de uso para procesar URLs de noticias y generar artículos."""

    def __init__(
        self,
        content_extractor: ContentExtractor,
        generated_articles_repo: GeneratedArticlesRepository,
        generated_posts_repo: GeneratedPostsRepository,
        ai_providers: AiProviders,
        *,
        social_truncator: Callable[..., str],
        post_editor: Callable[..., str],
        tts_text_processor: Any,
        cache_loader: Callable[..., tuple[Optional[str], str]],
        cache_saver: Callable[..., bool],
        translator: Callable[[str, str], str],
        tts_usecase: Any = None,
        use_ai: bool = True,
        model_provider: str = "gemini",
        ai_model=None,
        video_generator: Optional[VideoGeneratorPort] = None,
        force_extract: bool = False,
        cache_dir: Optional[Path] = None,
        copyright_domains: Optional[list[str]] = None,
        wp_site_url: str = "",
        wp_default_image_url: str = "",
    ):
        if ai_providers is None:
            raise ValueError("ai_providers es requerido")
        self.content_extractor = content_extractor
        self.generated_articles_repo = generated_articles_repo
        self.generated_posts_repo = generated_posts_repo
        self.use_ai = use_ai
        self.model_provider = model_provider
        self.ai_model = ai_model
        self._ai_providers = ai_providers
        self.article_generator = None
        self.video_generator = video_generator
        self.force_extract = force_extract
        self._cache_dir = cache_dir or Path(".")
        self._copyright_domains = copyright_domains or []
        self._wp_site_url = wp_site_url
        self._wp_default_image_url = wp_default_image_url
        self._social_truncator = social_truncator
        self._post_editor = post_editor
        self._tts_text_processor = tts_text_processor
        self._cache_loader = cache_loader
        self._cache_saver = cache_saver
        self._translator = translator
        self._tts_usecase = tts_usecase

    def _get_article_generator(self):
        if self.article_generator is None:
            self.article_generator = ArticleFromNewsUseCase(
                ai_providers=self._ai_providers,
                use_ai=self.use_ai,
                model_provider=self.model_provider,
                wp_site_url=self._wp_site_url,
                wp_default_image_url=self._wp_default_image_url,
                social_truncator=self._social_truncator,
                post_editor=self._post_editor,
                translator=self._translator,
            )
        return self.article_generator

    def _load_from_cache(self, url: str) -> Optional[tuple[str, Path]]:
        try:
            content, status = self._cache_loader(url, max_age_hours=24)
            if content and status == "cache_hit":
                cache_path = self._cache_dir / f"{hash(url)}.txt"
                return content, cache_path
            return None
        except Exception:
            return None

    def _save_to_cache(self, url: str, content: str):
        self._cache_saver(url, content, "news_to_news")

    def _extract_content(self, url: str) -> tuple[str, Path]:
        """Extrae contenido de la URL."""
        # Check cache only if force_extract is False
        if not self.force_extract:
            cached = self._load_from_cache(url)
            if cached:
                logger.info("[NEWS_TO_NEWS] Usando contenido desde caché")
                return cached

        if self.force_extract:
            logger.info("[NEWS_TO_NEWS] Forzando extracción fresca (omitiendo caché)")

        content, method, _titulo = self.content_extractor.extract(url)

        if content:
            self._save_to_cache(url, content)

        cache_path = self._cache_dir / f"{hash(url)}.txt"
        return content or "", cache_path

    def _generate_article(
        self, content: str, url: str, tema: str = "Noticias"
    ) -> Dict[str, Any]:
        """Genera artículo a partir del contenido."""
        generator = self._get_article_generator()
        return generator.execute(content, url, tema)

    def _generate_tweet(self, article_data: Dict) -> str:
        """Genera tweet a partir del artículo."""
        title = article_data.get("article", {}).get("title", "")
        url = article_data.get("article", {}).get("url", self._wp_site_url)
        tema = article_data.get("news_item", {}).get("tema", "Noticias")
        desc = article_data.get("article", {}).get("desc", "")[:200]

        try:
            model = self.ai_model
            if model is None:
                provider = self.model_provider if self.use_ai else "mock"
                model = self._ai_providers.adapter_factory(provider)

            agent = self._ai_providers.tweet_geopolitics_agent_factory(model)
            respuesta = agent.generate(title=title, tema=tema, context=desc)

            if respuesta.publishable:
                tweet = self._social_truncator(respuesta.text)
                if tweet:
                    logger.info(f"[NEWS_TO_NEWS] Tweet generado: {tweet[:80]}...")
                    return tweet
            else:
                logger.warning(
                    f"[NEWS_TO_NEWS] La IA no generó un tweet publicable para "
                    f"{title[:60]}...: {respuesta.reason[:160]}"
                )
        except Exception as e:
            logger.warning(f"[NEWS_TO_NEWS] Error generando tweet con IA: {e}")

        # Fallback: usar título + URL
        fallback_tweet = f"📰 {title[:150]}\n\nLeer más: {url}"
        tweet = self._social_truncator(fallback_tweet)
        logger.info(f"[NEWS_TO_NEWS] Tweet fallback generado: {tweet[:80]}...")
        return tweet

    def _save_outputs(self, article_data: Dict, content: str, content_path: Path):
        """Persiste artículo y post usando repositorios inyectados (DIP)."""
        article = article_data.get("article", {})
        post = article_data.get("post", {})

        try:
            # Save article via repository
            self.generated_articles_repo.save_all([dict(article)])
            logger.info("[NEWS_TO_NEWS] Artículo guardado en MongoDB")

            # Save post via repository
            tweet = post.get("tweet", "") if isinstance(post, dict) else ""
            original_url = article.get("original_url", "")
            self.generated_posts_repo.save_all([{"url": original_url, "tweet": tweet}])
            logger.info("[NEWS_TO_NEWS] Post guardado en MongoDB")
        except Exception as e:
            logger.error(f"[NEWS_TO_NEWS] Error persistiendo en MongoDB: {e}")

        article_file = content_path.with_suffix(".md")
        try:
            article_file.write_text(article.get("content", ""), encoding="utf-8")
        except Exception as e:
            logger.error(f"[NEWS_TO_NEWS] Error escribiendo artículo .md: {e}")
            raise

        return {}

    def process_url(self, url: str) -> Dict[str, Any]:
        """Procesa una URL de noticia y genera artículo completo."""
        logger.info(f"[NEWS_TO_NEWS] Iniciando procesamiento de: {url}")

        if check_copyright(url, self._copyright_domains):
            logger.warning(f"[NEWS_TO_NEWS] ⚠️ Posible riesgo de copyright: {url}")

        content, content_path = self._extract_content(url)

        if not content or len(content) < 100:
            raise ValueError(f"No se pudo extraer contenido de: {url}")

        article_data = self._generate_article(content, url)

        tweet_text = self._generate_tweet(article_data)

        # Step 5: Text-to-Speech (inserted after article generation)
        logger.info("[NEWS_TO_NEWS] Generando audio TTS del artículo...")
        try:
            if self._tts_usecase is not None:
                article = article_data.get("article", {})
                article = self._tts_usecase.execute(article)
                article_data["article"] = article

                if article.get("tts_audio_path"):
                    logger.info(
                        f"[NEWS_TO_NEWS] Audio TTS generado: {article['tts_audio_path']}"
                    )
                else:
                    logger.warning("[NEWS_TO_NEWS] No se generó audio TTS")
            else:
                logger.info("[NEWS_TO_NEWS] TTS omitido (tts_usecase no inyectado)")
        except Exception as e:
            logger.warning(f"[NEWS_TO_NEWS] Error en generación TTS (no bloquea): {e}")

        # Step 6: Video Generation (from TTS audio + random image)
        logger.info("[NEWS_TO_NEWS] Generando video a partir del audio TTS...")
        try:
            if self.video_generator and self.video_generator.is_available():
                article = article_data.get("article", {})
                tts_audio_path = article.get("tts_audio_path")
                if tts_audio_path and os.path.exists(tts_audio_path):
                    video_path = self.video_generator.create_video_from_audio(
                        audio_path=tts_audio_path,
                        image=article.get("image_url"),
                    )
                    if video_path:
                        article["generated_video_path"] = video_path
                        article_data["article"] = article
                        logger.info(f"[NEWS_TO_NEWS] Video generado: {video_path}")
                    else:
                        logger.warning("[NEWS_TO_NEWS] No se pudo generar el video")
                else:
                    logger.warning(
                        "[NEWS_TO_NEWS] No hay audio TTS disponible para generar video"
                    )
            else:
                logger.warning("[NEWS_TO_NEWS] Video generator not available")
        except Exception as e:
            logger.warning(
                f"[NEWS_TO_NEWS] Error en generación de video (no bloquea): {e}"
            )

        saved_files = self._save_outputs(article_data, content, content_path)

        result = {
            "source_content": content,
            "content_file": str(content_path),
            "article": article_data.get("article", {}).get("content", ""),
            "article_file": saved_files.get("article_file", ""),
            "post": tweet_text,
            "article_data": article_data,
            "mode": self.model_provider,
            "saved_files": saved_files,
        }

        logger.info("[NEWS_TO_NEWS] ✅ Procesamiento completado")
        return result


def process_news_url(
    url: str,
    content_extractor: ContentExtractor,
    generated_articles_repo: GeneratedArticlesRepository,
    generated_posts_repo: GeneratedPostsRepository,
    *,
    ai_providers: AiProviders,
    social_truncator: Callable[..., str],
    post_editor: Callable[..., str],
    tts_text_processor: Any,
    cache_loader: Callable[..., tuple[Optional[str], str]],
    cache_saver: Callable[..., bool],
    translator: Callable[[str, str], str],
    tts_usecase: Any = None,
    model_provider: str = "gemini",
    use_ai: bool = True,
    video_generator: Optional[VideoGeneratorPort] = None,
    force_extract: bool = False,
    cache_dir: Optional[Path] = None,
    copyright_domains: Optional[list[str]] = None,
    wp_site_url: str = "",
    wp_default_image_url: str = "",
) -> Dict[str, Any]:
    """Función principal para procesar URL de noticia."""
    processor = NewsToNewsUseCase(
        content_extractor=content_extractor,
        generated_articles_repo=generated_articles_repo,
        generated_posts_repo=generated_posts_repo,
        ai_providers=ai_providers,
        model_provider=model_provider,
        use_ai=use_ai,
        video_generator=video_generator,
        force_extract=force_extract,
        cache_dir=cache_dir,
        copyright_domains=copyright_domains,
        wp_site_url=wp_site_url,
        wp_default_image_url=wp_default_image_url,
        social_truncator=social_truncator,
        post_editor=post_editor,
        tts_text_processor=tts_text_processor,
        cache_loader=cache_loader,
        cache_saver=cache_saver,
        translator=translator,
        tts_usecase=tts_usecase,
    )
    return processor.process_url(url)


