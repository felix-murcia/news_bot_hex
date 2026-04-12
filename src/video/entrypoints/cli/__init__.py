from config.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger("video_bot")
from src.video.infrastructure.adapters.video_fetcher import VideoFetcher, download_video
from src.video.application.usecases.video_to_news import process_video_url
from src.video.application.usecases.article_from_video import run_from_video
from src.video.application.usecases.video_pipeline import VideoPipelineUseCase
from config.settings import Settings


def main_fetch():
    """Punto de entrada para descargar videos."""
    import sys

    if len(sys.argv) < 3:
        print("Uso: python -m src.video.entrypoints.cli fetch <url> [output_dir]")
        return

    url = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else None

    result = download_video(url, output_dir)
    if result:
        logger.info(f"[VIDEO] Video descargado: {result}")
        print(f"✅ {result}")
    else:
        logger.error(f"[VIDEO] Error descargando video")
        print("❌ Error")


def main_info():
    """Punto de entrada para obtener información del video."""
    import sys

    if len(sys.argv) < 3:
        print("Uso: python -m src.video.entrypoints.cli info <url>")
        return

    url = sys.argv[2]
    fetcher = VideoFetcher()
    info = fetcher.get_info(url)

    if info:
        logger.info(f"[VIDEO] Info obtenida: {info.get('title')}")
        print(f"📹 {info.get('title')}")
        print(f"👤 {info.get('uploader')}")
        print(f"⏱️ {info.get('duration')}s")
    else:
        logger.error(f"[VIDEO] Error obteniendo info")
        print("❌ Error")


def main_video_to_news():
    """Punto de entrada para procesar video y generar artículo."""
    import sys

    if len(sys.argv) < 3:
        print("Uso: python -m src.video.entrypoints.cli process <video_url>")
        return

    url = sys.argv[2]
    result = process_video_url(url)

    logger.info(f"[VIDEO] Procesado: {url}")
    print(f"✅ Artículo: {len(result.get('article', ''))} caracteres")
    print(f"🐦 Tweet: {result.get('post', '')[:80]}...")


def main_article_from_video():
    """Punto de entrada para generar artículo desde transcripción."""
    import sys

    if len(sys.argv) < 3:
        print(
            f"Uso: python -m src.video.entrypoints.cli article <transcript_file> [--llm {'|'.join(Settings.SUPPORTED_AI_PROVIDERS)}]"
        )
        return

    transcript_file = sys.argv[2]
    llm_provider = Settings.AI_PROVIDER

    for i, arg in enumerate(sys.argv[3:]):
        if arg == "--llm" and i + 3 < len(sys.argv):
            llm_provider = sys.argv[i + 4]

    with open(transcript_file, "r", encoding="utf-8") as f:
        transcript = f.read()

    result = run_from_video(
        transcript=transcript, url="", tema="Videos", llm_provider=llm_provider
    )

    logger.info(f"[ARTICLE_VIDEO] Artículo generado")
    print(f"✅ Título: {result['article']['title']}")
    print(
        f"📈 Estructura: {result['stats']['parrafos']}p/{result['stats']['subtitulos']}h2"
    )


def main_wordpress():
    """Publicar en WordPress."""
    from src.shared.adapters.wordpress_publisher import run as run_wordpress

    result = run_wordpress()
    logger.info(f"[WORDPRESS] Resultado: {result}")
    print(f"[WORDPRESS] Publicados: {result.get('published', 0)}")


def main_bluesky():
    """Publicar en Bluesky."""
    from src.shared.adapters.bluesky_publisher import run as run_bluesky

    result = run_bluesky()
    logger.info(f"[BLUESKY] Resultado: {result}")
    print(f"[BLUESKY] Publicados: {result.get('published', 0)}")


def main_mastodon():
    """Publicar en Mastodon."""
    from src.shared.adapters.mastodon_publisher import run as run_mastodon

    result = run_mastodon()
    logger.info(f"[MASTODON] Resultado: {result}")
    print(f"[MASTODON] Publicados: {result.get('published', 0)}")


def main_facebook():
    """Publicar en Facebook."""
    from src.shared.adapters.facebook_publisher import run as run_facebook

    result = run_facebook()
    logger.info(f"[FACEBOOK] Resultado: {result}")
    print(f"[FACEBOOK] Publicados: {result.get('published', 0)}")


def main_full_pipeline():
    """Punto de entrada para ejecutar el pipeline completo de video (10 pasos)."""
    import sys

    if len(sys.argv) < 3:
        print("Uso: python -m src.video.entrypoints.cli full <video_url>")
        return

    url = sys.argv[2]
    llm_provider = Settings.AI_PROVIDER

    for i, arg in enumerate(sys.argv):
        if arg == "--llm" and i + 1 < len(sys.argv):
            llm_provider = sys.argv[i + 1]

    logger.info("=== INICIO VIDEO PIPELINE (10 PASOS) ===")

    logger.info("[1/10] Obteniendo información del video...")
    fetcher = VideoFetcher()
    info = fetcher.get_info(url)
    if not info:
        logger.error("[VIDEO] No se pudo obtener info del video")
        print("❌ Error obteniendo info")
        return
    logger.info(f"[VIDEO] {info.get('title')}")

    logger.info("[2/10] Procesando video y generando contenido...")
    result = process_video_url(url)
    logger.info("[VIDEO] Contenido generado")

    logger.info("[3/10] Generando tweets/posts...")
    tema = result.get("tema", "Videos")
    article_result = run_from_video(
        transcript=result.get("transcript", ""),
        url=url,
        tema=tema,
        llm_provider=llm_provider,
    )
    logger.info(f"[ARTICLE_VIDEO] Tweet generado: {article_result['tweet'][:50]}...")

    logger.info("[4/10] Generando artículos profesionales en español...")
    logger.info(f"[ARTICLE_VIDEO] Artículo: {article_result['article']['title']}")

    logger.info("[5/10] Buscando imágenes en Unsplash...")
    from src.shared.adapters.unsplash_fetcher import run as run_unsplash

    run_unsplash()
    logger.info("[VIDEO] Imágenes Unsplash buscadas")

    logger.info("[6/10] Buscando imágenes en Google Images...")
    from src.shared.adapters.google_images_fetcher import run as run_google

    run_google()
    logger.info("[VIDEO] Imágenes Google buscadas")

    logger.info("[7/10] Enriqueciendo con imágenes...")
    from src.shared.adapters.image_enricher import run as run_image_enricher

    run_image_enricher()
    logger.info("[VIDEO] Imágenes enrichment completado")

    logger.info("[8/10] Publicando en WordPress...")
    main_wordpress()
    logger.info("[VIDEO] WordPress publicado")

    logger.info("[9/10] Publicando en redes sociales...")
    main_facebook()
    main_bluesky()
    main_mastodon()
    logger.info("[VIDEO] Redes sociales publicadas")

    logger.info("[10/10] Guardando en cache...")
    logger.info("=== VIDEO PIPELINE COMPLETO (10 PASOS) ===")

    print(f"✅ Video procesado: {info.get('title')}")
    print(f"📰 Artículo: {article_result['article'].get('title', 'Sin título')}")
    print(f"🐦 Tweet: {article_result.get('tweet', '')[:80]}...")


def main_pipeline():
    """Punto de entrada para ejecutar el pipeline completo de video (4 pasos - legacy)."""
    import sys

    if len(sys.argv) < 3:
        print("Uso: python -m src.video.entrypoints.cli pipeline <video_url>")
        return

    url = sys.argv[2]
    llm_provider = Settings.AI_PROVIDER

    for i, arg in enumerate(sys.argv):
        if arg == "--llm" and i + 1 < len(sys.argv):
            llm_provider = sys.argv[i + 1]

    logger.info("=== INICIO VIDEO PIPELINE ===")

    logger.info("[1/4] Obteniendo información del video...")
    fetcher = VideoFetcher()
    info = fetcher.get_info(url)
    if not info:
        logger.error("[VIDEO] No se pudo obtener info del video")
        print("❌ Error obteniendo info")
        return
    logger.info(f"[VIDEO] {info.get('title')}")

    logger.info("[2/4] Procesando video y generando contenido...")
    result = process_video_url(url)
    logger.info("[VIDEO] Contenido generado")

    logger.info("[3/4] Generando artículo...")
    tema = result.get("tema", "Videos")
    article_result = run_from_video(
        transcript=result.get("transcript", ""),
        url=url,
        tema=tema,
        llm_provider=llm_provider,
    )
    logger.info("[ARTICLE_VIDEO] Artículo generado")

    logger.info("[4/4] Generando tweet...")
    print(f"✅ Video procesado: {info.get('title')}")
    print(f"📰 Artículo: {article_result['article'].get('title', 'Sin título')}")
    print(f"🐦 Tweet: {article_result.get('tweet', '')[:80]}...")

    logger.info("=== VIDEO PIPELINE COMPLETO ===")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "fetch":
            main_fetch()
        elif sys.argv[1] == "info":
            main_info()
        elif sys.argv[1] == "process":
            main_video_to_news()
        elif sys.argv[1] == "article":
            main_article_from_video()
        elif sys.argv[1] == "pipeline":
            main_pipeline()
        elif sys.argv[1] == "full":
            main_full_pipeline()
        elif sys.argv[1] == "wordpress":
            main_wordpress()
        elif sys.argv[1] == "bluesky":
            main_bluesky()
        elif sys.argv[1] == "mastodon":
            main_mastodon()
        elif sys.argv[1] == "facebook":
            main_facebook()
        else:
            print(
                "Uso: python -m src.video.entrypoints.cli [fetch|info|process|article|pipeline|full|wordpress|bluesky|mastodon|facebook] <args>"
            )
    else:
        print(
            "Uso: python -m src.video.entrypoints.cli [fetch|info|process|article|pipeline|full|wordpress|bluesky|mastodon|facebook] <args>"
        )