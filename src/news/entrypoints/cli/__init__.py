import logging
from src.news.application.usecases import (
    FetchRSSNewsUseCase,
    VerifyNewsUseCase,
    FullVerifyNewsUseCase,
)
from src.news.application.usecases.soft_verify import (
    main as main_soft_verify,
    clear_verified_news_wrapper,
)
from src.news.application.usecases.article_from_news import (
    run_from_news,
    main as main_article_from_news,
)
from src.news.application.usecases.article import (
    run as run_article_gemini,
    main as main_article_gemini,
)
from src.news.application.usecases.content import (
    run_content as run_content_gemini,
    main as main_content_gemini,
)
from src.news.application.usecases.news_to_news import (
    process_news_url,
    main as main_news_to_news,
)
from src.shared.adapters.bluesky_publisher import run as run_bluesky, BlueskyPublisher
from src.shared.adapters.facebook_publisher import (
    run as run_facebook,
    FacebookPublisher,
)
from src.shared.adapters.mastodon_publisher import (
    run as run_mastodon,
    MastodonPublisher,
)
from src.shared.adapters.wordpress_publisher import (
    run as run_wordpress,
    WordPressPublisher,
)
from src.news.infrastructure.adapters import (
    MongoRSSSourceRepository,
    MongoArticleRepository,
    FeedparserRSSFetcher,
    MongoVerifiedNewsRepository,
    MongoPublishedUrlsRepository,
    MongoKeywordsRepository,
    MongoScoringConfigRepository,
    JinaContentExtractor,
    DummyFakeNewsModel,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")


def main_rss():
    """Punto de entrada para obtener noticias RSS."""
    source_repo = MongoRSSSourceRepository()
    article_repo = MongoArticleRepository()
    rss_fetcher = FeedparserRSSFetcher()

    use_case = FetchRSSNewsUseCase(source_repo, article_repo, rss_fetcher)
    result = use_case.execute()

    if result["status"] == "error":
        logger.error(f"[RSS] {result['message']}")
        return

    logger.info(
        f"[RSS] TOTAL: {result['new_articles']} nuevas + {result['total_articles'] - result['new_articles']} existentes = "
        f"{result['total_articles']} artículos → MongoDB (raw_news)"
    )


def main_verify():
    """Punto de entrada para verificar noticias (desde generated_news_articles.json)."""
    verified_repo = MongoVerifiedNewsRepository()
    use_case = VerifyNewsUseCase(verified_repo)
    result = use_case.execute()

    if result["status"] == "error":
        logger.error(f"[VERIFIER] {result['message']}")
        return

    logger.info(
        f"[VERIFIER] ✅ GUARDADO: {result['articles']} artículos en MongoDB (verified_news)"
    )


def main_full_verify():
    """Punto de entrada para verificación completa de noticias."""
    article_repo = MongoArticleRepository()
    verified_repo = MongoVerifiedNewsRepository()
    published_urls_repo = MongoPublishedUrlsRepository()
    keywords_repo = MongoKeywordsRepository()
    scoring_config_repo = MongoScoringConfigRepository()
    content_extractor = JinaContentExtractor()
    fake_news_model = DummyFakeNewsModel()

    use_case = FullVerifyNewsUseCase(
        article_repo=article_repo,
        verified_repo=verified_repo,
        published_urls_repo=published_urls_repo,
        keywords_repo=keywords_repo,
        scoring_config_repo=scoring_config_repo,
        content_extractor=content_extractor,
        fake_news_model=fake_news_model,
    )

    result = use_case.execute()

    if result["status"] == "error":
        logger.error(f"[VERIFIER] {result['message']}")
        return

    logger.info(
        f"[VERIFIER] Procesados: {result.get('processed', 0)}, "
        f"Verificados: {result.get('verified', 0)}, "
        f"Guardados: {result.get('saved', 0)}"
    )


def main_verifier():
    """Punto de entrada para verificación completa de noticias (equivalente a verifier.py original)."""
    main_full_verify()


def main_soft():
    """Punto de entrada para verificación soft."""
    result = main_soft_verify()
    if result["status"] == "error":
        logger.error(f"[SOFT] {result.get('message', 'Error')}")
        return
    logger.info(
        f"[SOFT] ✅ Noticia seleccionada: {result.get('title', '')} "
        f"(score={result.get('score', 0)}, strategy={result.get('strategy', '')})"
    )


def main_article():
    """Punto de entrada para generar artículo desde noticia."""
    main_article_from_news()


def main_article():
    """Punto de entrada para generar artículo desde noticia."""
    main_article_from_news()


def main_provider():
    """Punto de entrada para generar artículos con IA (multi-proveedor)."""
    import argparse

    parser = argparse.ArgumentParser(description="Generador de artículos con IA")
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")
    parser.add_argument("--limit", type=int, default=1, help="Límite de artículos")
    parser.add_argument(
        "--model",
        type=str,
        default="openrouter",
        choices=["gemini", "openrouter", "local", "mock"],
        help="Modelo de IA a usar",
    )

    args = parser.parse_args()

    from src.news.application.usecases.article import run

    results = run(
        limit=args.limit, use_gemini=not args.local, model_provider=args.model
    )

    if results:
        print(f"✅ {len(results)} artículo(s) generado(s)")
    else:
        print("⚠️ No se generaron artículos")


def main_content():
    """Punto de entrada para generar contenido (tweets)."""
    main_content_gemini()


def main_news_to_news():
    """Punto de entrada para procesar URLs de noticias."""
    import sys

    if len(sys.argv) > 2:
        url = sys.argv[2]
        result = process_news_url(url)
        logger.info(f"[NEWS_TO_NEWS] Procesado: {result.get('article_file', '')}")
    else:
        print("Uso: python -m src.news.entrypoints.cli news_to_news <url>")


def main_bluesky():
    """Punto de entrada para publicar en Bluesky."""
    result = run_bluesky()
    logger.info(f"[BLUESKY] Resultado: {result}")
    print(f"[BLUESKY] Publicados: {result.get('published', 0)}")


def main_facebook():
    """Punto de entrada para publicar en Facebook."""
    result = run_facebook()
    logger.info(f"[FACEBOOK] Resultado: {result}")
    print(f"[FACEBOOK] Publicados: {result.get('published', 0)}")


def main_mastodon():
    """Punto de entrada para publicar en Mastodon."""
    result = run_mastodon()
    logger.info(f"[MASTODON] Resultado: {result}")
    print(f"[MASTODON] Publicados: {result.get('published', 0)}")


def main_wordpress():
    """Punto de entrada para publicar en WordPress."""
    result = run_wordpress()
    logger.info(f"[WORDPRESS] Resultado: {result}")
    print(f"[WORDPRESS] Publicados: {result.get('published', 0)}")


def main_pipeline():
    """Punto de entrada para ejecutar el pipeline completo."""
    logger.info("=== INICIO PIPELINE COMPLETO ===")

    logger.info("[1/10] Obteniendo RSS...")
    main_rss()

    logger.info("[2/10] Verificando y filtrando noticias...")
    main_full_verify()

    logger.info("[3/10] Generando tweets/posts desde noticias verificadas...")
    from src.news.application.usecases.content import run_content

    run_content(use_gemini=True, mode="news")

    logger.info("[4/10] Generando artículos profesionales en español con Gemini...")
    from src.news.application.usecases.article import run as run_article_gemini

    run_article_gemini(use_gemini=True)

    logger.info("[5/10] Buscando imágenes en Unsplash...")
    from src.shared.adapters.unsplash_fetcher import run as run_unsplash

    run_unsplash()

    logger.info("[6/10] Buscando imágenes en Google Images...")
    from src.shared.adapters.google_images_fetcher import run as run_google

    run_google()

    logger.info("[7/10] Enriqueciendo con imágenes...")
    from src.shared.adapters.image_enricher import run as run_image_enricher

    run_image_enricher()

    logger.info("[8/10] Publicando en WordPress...")
    main_wordpress()

    logger.info("[9/10] Publicando en redes sociales (usando URL de WordPress)...")
    main_facebook()
    main_bluesky()
    main_mastodon()

    logger.info("=== PIPELINE COMPLETO FINALIZADO ===")


def reload_sources():
    """Recarga fuentes RSS desde MongoDB."""
    from src.news.application.usecases import reload_sources as _reload

    return _reload()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "rss":
            main_rss()
        elif sys.argv[1] == "verify":
            main_verify()
        elif sys.argv[1] == "full":
            main_full_verify()
        elif sys.argv[1] == "verifier":
            main_verifier()
        elif sys.argv[1] == "soft":
            main_soft()
        elif sys.argv[1] == "article":
            main_article()
        elif sys.argv[1] == "provider":
            main_provider()
        elif sys.argv[1] == "content":
            main_content()
        elif sys.argv[1] == "news_to_news":
            main_news_to_news()
        elif sys.argv[1] == "bluesky":
            main_bluesky()
        elif sys.argv[1] == "facebook":
            main_facebook()
        elif sys.argv[1] == "mastodon":
            main_mastodon()
        elif sys.argv[1] == "wordpress":
            main_wordpress()
        elif sys.argv[1] == "pipeline":
            main_pipeline()
        else:
            print(
                "Uso: python -m src.news.entrypoints.cli [rss|verify|full|verifier|soft|article|provider|content|news_to_news|bluesky|facebook|mastodon|wordpress|pipeline]"
            )
    else:
        main_rss()
