import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional

from config.settings import Settings
from src.news.domain.ports import ContentExtractor
from config.logging_config import get_logger
from src.shared.domain.ports.video_generator_port import VideoGeneratorPort

logger = get_logger("news_bot.usecase.news_to_news")

DATA_DIR = Settings.DATA_DIR
CACHE_DIR = Settings.CACHE_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def check_copyright(url: str) -> bool:
    """Check copyright risk for a URL."""
    url_lower = url.lower()
    return any(domain.lower() in url_lower for domain in Settings.COPYRIGHT_DOMAINS)


class NewsToNewsUseCase:
    """Caso de uso para procesar URLs de noticias y generar artículos."""

    def __init__(
        self,
        content_extractor: ContentExtractor,
        use_ai: bool = True,
        model_provider: str = Settings.AI_PROVIDER,
        ai_config: Optional[dict] = None,
        ai_model=None,
        video_generator: Optional[VideoGeneratorPort] = None,
        force_extract: bool = False,
    ):
        self.content_extractor = content_extractor
        self.use_ai = use_ai
        self.model_provider = model_provider
        self.ai_config = ai_config or {}
        self.ai_model = ai_model
        self.article_generator = None
        self.video_generator = video_generator
        self.force_extract = force_extract

    def _get_article_generator(self):
        if self.article_generator is None:
            from src.news.application.usecases.article_from_news import (
                ArticleFromNewsUseCase,
            )

            self.article_generator = ArticleFromNewsUseCase(
                use_ai=self.use_ai,
                model_provider=self.model_provider,
                ai_config=self.ai_config,
            )
        return self.article_generator

    def _load_from_cache(self, url: str) -> Optional[tuple[str, Path]]:
        try:
            from src.shared.adapters.cache_manager import load_content_from_cache

            content, status = load_content_from_cache(url, max_age_hours=24)
            if content and status == "cache_hit":
                cache_path = CACHE_DIR / f"{hash(url)}.txt"
                return content, cache_path
            return None
        except Exception:
            return None

    def _save_to_cache(self, url: str, content: str):
        try:
            from src.shared.adapters.cache_manager import save_content_to_cache

            save_content_to_cache(url, content, "news_to_news")
        except Exception:
            pass

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

        content, method = self.content_extractor.extract(url)

        if content:
            self._save_to_cache(url, content)

        cache_path = CACHE_DIR / f"{hash(url)}.txt"
        return content or "", cache_path

    def _generate_article(
        self, content: str, url: str, tema: str = "Noticias"
    ) -> Dict[str, Any]:
        """Genera artículo a partir del contenido."""
        generator = self._get_article_generator()
        return generator.execute(content, url, tema)

    def _generate_tweet(self, article_data: Dict) -> str:
        """Genera tweet a partir del artículo."""
        from src.shared.adapters.ai.agents import TweetGeopoliticsAgent
        from src.shared.adapters.social_post_adapter import truncate_social_post

        title = article_data.get("article", {}).get("title", "")
        url = article_data.get("article", {}).get("url", Settings.WP_SITE_URL)
        tema = article_data.get("news_item", {}).get("tema", "Noticias")
        desc = article_data.get("article", {}).get("desc", "")[:200]

        try:
            model = self.ai_model
            if model is None:
                # Fallback: lazy-load AI model if not injected (TODO: refactor to require injection)
                from src.shared.adapters.ai.ai_factory import get_ai_adapter
                provider = self.model_provider if self.use_ai else "mock"
                model = get_ai_adapter(provider, self.ai_config)

            agent = TweetGeopoliticsAgent(model)
            tweet = agent.generate(title=title, tema=tema, context=desc)
            tweet = truncate_social_post(tweet)

            if tweet:
                logger.info(f"[NEWS_TO_NEWS] Tweet generado: {tweet[:80]}...")
                return tweet
        except Exception as e:
            logger.warning(f"[NEWS_TO_NEWS] Error generando tweet con IA: {e}")

        # Fallback: usar título + URL
        fallback_tweet = f"📰 {title[:150]}\n\nLeer más: {url}"
        tweet = truncate_social_post(fallback_tweet)
        logger.info(f"[NEWS_TO_NEWS] Tweet fallback generado: {tweet[:80]}...")
        return tweet

    def _save_outputs(self, article_data: Dict, content: str, content_path: Path):
        """Guarda los outputs en archivos."""
        article = article_data.get("article", {})
        posts = article_data.get("post", {})

        articles_path = DATA_DIR / "generated_news_articles.json"
        posts_path = DATA_DIR / "generated_news_posts.json"

        with open(articles_path, "w", encoding="utf-8") as f:
            json.dump([article], f, indent=2, ensure_ascii=False)

        with open(posts_path, "w", encoding="utf-8") as f:
            json.dump([posts], f, indent=2, ensure_ascii=False)

        logger.info(f"[NEWS_TO_NEWS] Archivos guardados en {DATA_DIR}")

        article_file = content_path.with_suffix(".md")
        try:
            article_file.write_text(article.get("content", ""), encoding="utf-8")
        except Exception:
            pass

        return {
            "article_file": str(articles_path),
            "post_file": str(posts_path),
        }

    def process_url(self, url: str) -> Dict[str, Any]:
        """Procesa una URL de noticia y genera artículo completo."""
        logger.info(f"[NEWS_TO_NEWS] Iniciando procesamiento de: {url}")

        if check_copyright(url):
            logger.warning(f"[NEWS_TO_NEWS] ⚠️ Posible riesgo de copyright: {url}")

        content, content_path = self._extract_content(url)

        if not content or len(content) < 100:
            raise ValueError(f"No se pudo extraer contenido de: {url}")

        article_data = self._generate_article(content, url)

        tweet_text = self._generate_tweet(article_data)

        # Step 5: Text-to-Speech (inserted after article generation)
        logger.info("[NEWS_TO_NEWS] Generando audio TTS del artículo...")
        try:
            from src.shared.application.usecases.tts_from_article import (
                TTSFromArticleUseCase,
            )

            article = article_data.get("article", {})
            article = TTSFromArticleUseCase().execute(article)
            article_data["article"] = article

            if article.get("tts_audio_path"):
                logger.info(
                    f"[NEWS_TO_NEWS] Audio TTS generado: {article['tts_audio_path']}"
                )
            else:
                logger.warning("[NEWS_TO_NEWS] No se generó audio TTS")
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
                        audio_path=tts_audio_path
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
            "article_file": saved_files["article_file"],
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
    model_provider: str = Settings.AI_PROVIDER,
    use_ai: bool = True,
    ai_config: Optional[dict] = None,
    video_generator: Optional[VideoGeneratorPort] = None,
    force_extract: bool = False,
) -> Dict[str, Any]:
    """Función principal para procesar URL de noticia."""
    processor = NewsToNewsUseCase(
        content_extractor=content_extractor,
        model_provider=model_provider,
        use_ai=use_ai,
        ai_config=ai_config,
        video_generator=video_generator,
        force_extract=force_extract,
    )
    return processor.process_url(url)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Procesar URL de noticia y generar artículo"
    )
    parser.add_argument("url", type=str, help="URL de la noticia")
    parser.add_argument(
        "--debug", action="store_true", help="Mostrar información de depuración"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=Settings.AI_PROVIDER,
        choices=Settings.SUPPORTED_AI_PROVIDERS,
        help="Modelo de IA a usar",
    )
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")
    parser.add_argument(
        "--force-extract",
        action="store_true",
        help="Omitir caché y forzar extracción fresca con Jina",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("📰 NEWS_TO_NEWS - Procesador de noticias web")
    print("=" * 60)
    print(f"URL: {args.url}")
    print(f"Modelo: {args.model}")
    print()

    try:
        result = process_news_url(
            url=args.url,
            model_provider=args.model,
            use_ai=not args.local,
            force_extract=args.force_extract,
        )

        print("✅ PROCESAMIENTO COMPLETADO")
        print(f"📝 Contenido extraído: {len(result['source_content'])} caracteres")
        print(f"📄 Artículo: {len(result['article'])} caracteres")
        print(f"🐦 Tweet generado: {result['post'][:100]}...")

        print("\n📁 ARCHIVOS GENERADOS:")
        articles_path = DATA_DIR / "generated_news_articles.json"
        if articles_path.exists():
            print(f"  ✅ generated_news_articles.json")

        posts_path = DATA_DIR / "generated_news_posts.json"
        if posts_path.exists():
            print(f"  ✅ generated_news_posts.json")

        print("\n" + "=" * 60)
        print("✅ PRUEBA COMPLETADA")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
