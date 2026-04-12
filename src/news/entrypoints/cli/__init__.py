from config.logging_config import setup_logging, get_logger
from config.settings import Settings

setup_logging()
logger = get_logger("news_bot.pipeline")

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
    ClassicNewsValidatorAdapter,
)


def main_rss():
    """Punto de entrada para obtener noticias RSS."""
    source_repo = MongoRSSSourceRepository()
    article_repo = MongoArticleRepository()
    rss_fetcher = FeedparserRSSFetcher()

    use_case = FetchRSSNewsUseCase(source_repo, article_repo, rss_fetcher)
    result = use_case.execute()

    if result["status"] == "error":
        logger.error(f"[RSS] Error: {result['message']}")
        return result

    total = result.get('total_articles', 0)
    new = result.get('new_articles', 0)
    existing = total - new
    logger.info(
        f"[RSS] Capturadas {total} noticias ({new} nuevas, {existing} existentes) desde fuentes RSS → MongoDB"
    )
    return result


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

    # Classic validator: TF-IDF + LogisticRegression (CPU, fast)
    fake_news_model = ClassicNewsValidatorAdapter()

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
        logger.error(f"[VERIFIER] Error: {result['message']}")
        return result

    logger.info(
        f"[VERIFIER] Procesadas {result.get('processed', 0)} noticias → "
        f"{result.get('verified', 0)} verificadas, {result.get('saved', 0)} guardadas en MongoDB"
    )
    return result


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


def main_provider():
    """Punto de entrada para generar artículos con IA (multi-proveedor)."""
    import argparse

    parser = argparse.ArgumentParser(description="Generador de artículos con IA")
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")
    parser.add_argument("--limit", type=int, default=1, help="Límite de artículos")
    parser.add_argument(
        "--model",
        type=str,
        default=Settings.AI_PROVIDER,
        choices=Settings.SUPPORTED_AI_PROVIDERS,
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
    logger.info(f"[BLUESKY] Publicación finalizada. Publicados: {result.get('published', 0)}")
    return result


def main_facebook():
    """Punto de entrada para publicar en Facebook."""
    result = run_facebook()
    logger.info(f"[FACEBOOK] Publicación finalizada. Publicados: {result.get('published', 0)}")
    return result


def main_mastodon():
    """Punto de entrada para publicar en Mastodon."""
    result = run_mastodon()
    logger.info(f"[MASTODON] Publicación finalizada. Publicados: {result.get('published', 0)}")
    return result


def main_wordpress():
    """Punto de entrada para publicar en WordPress."""
    result = run_wordpress()
    logger.info(f"[WORDPRESS] Publicación finalizada. Publicados: {result.get('published', 0)}")
    return result


def main_pipeline():
    """Punto de entrada para ejecutar el pipeline completo."""
    import time
    pipeline_start = time.time()

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETO — INICIO")
    logger.info("=" * 60)

    # Step 1: RSS Fetch
    logger.info("[RSS] Iniciando captura de fuentes RSS...")
    result_rss = main_rss()
    logger.info("[RSS] Finalizada captura de fuentes RSS.")

    # Step 2: Full Verification
    logger.info("[VERIFIER] Iniciando verificación completa de noticias...")
    main_full_verify()
    logger.info("[VERIFIER] Verificación completa finalizada.")

    # Step 3: Generate tweets/posts
    logger.info("[CONTENT] Iniciando generación de tweets/posts desde noticias verificadas...")
    from src.news.application.usecases.content import run_content
    posts = run_content(use_gemini=True, mode="news")
    logger.info(f"[CONTENT] Finalizada generación de {len(posts)} post(s).")

    # Step 4: Generate articles
    logger.info("[ARTICLE] Iniciando generación de artículos profesionales en español...")
    from src.news.application.usecases.article import run as run_article_gemini
    articles = run_article_gemini(use_gemini=True)
    logger.info(f"[ARTICLE] Finalizada generación de {len(articles)} artículo(s).")

    # Step 5: Unsplash images
    logger.info("[IMAGE] Iniciando búsqueda de imágenes en Unsplash...")
    from src.shared.adapters.unsplash_fetcher import run as run_unsplash
    run_unsplash()
    logger.info("[IMAGE] Búsqueda en Unsplash finalizada.")

    # Step 6: Google Images
    logger.info("[IMAGE] Iniciando búsqueda de imágenes en Google Images...")
    from src.shared.adapters.google_images_fetcher import run as run_google
    run_google()
    logger.info("[IMAGE] Búsqueda en Google Images finalizada.")

    # Step 7: Image enrichment
    logger.info("[IMAGE] Iniciando enriquecimiento y selección de imágenes...")
    from src.shared.adapters.image_enricher import run as run_image_enricher
    run_image_enricher()
    logger.info("[IMAGE] Enriquecimiento de imágenes finalizado.")

    # Step 8: WordPress
    logger.info("[WORDPRESS] Iniciando publicación en WordPress...")
    wp_result = main_wordpress()
    logger.info(f"[WORDPRESS] Publicación en WordPress finalizada. Publicados: {wp_result.get('published', 0)}")

    # Step 9: Social Media
    logger.info("[SOCIAL] Iniciando publicación en redes sociales...")
    main_facebook()
    main_bluesky()
    main_mastodon()
    logger.info("[SOCIAL] Publicación en redes sociales finalizada.")

    elapsed = time.time() - pipeline_start
    logger.info("=" * 60)
    logger.info(f"PIPELINE COMPLETO — FINALIZADO en {elapsed:.1f}s")
    logger.info("=" * 60)


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
