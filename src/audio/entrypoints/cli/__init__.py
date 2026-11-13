from config.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger("audio_bot")
from src.audio.infrastructure.adapters.audio_fetcher import AudioFetcher, download_audio
from src.audio.application.usecases.audio_to_news import AudioToNewsUseCase
from src.shared.application.usecases.article_from_transcript import run_from_transcript
from src.shared.infrastructure.composition_root import (
    create_ai_providers,
    create_debug_output_repository,
)
from config.settings import Settings


def main_fetch():
    """Punto de entrada para descargar audio."""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m src.audio.entrypoints.cli fetch <url>")
        return

    url = sys.argv[2]
    result = download_audio(url)
    if result:
        logger.info(f"[AUDIO] Audio descargado: {result}")
        print(f"✅ {result}")
    else:
        logger.error(f"[AUDIO] Error descargando audio")
        print("❌ Error")


def main_audio_to_news():
    """Punto de entrada para procesar audio y generar artículo."""
    import argparse
    import sys

    from config.settings import Settings
    from src.audio.infrastructure.adapters.audio_fetcher import download_audio, transcribe_audio
    from src.shared.adapters.audio_converter import AudioConverter

    if len(sys.argv) < 3:
        print(
            "Uso: python -m src.audio.entrypoints.cli process <audio_url> "
            "[--model X] [--local]"
        )
        return

    url = sys.argv[2]

    parser = argparse.ArgumentParser(
        description="Procesar audio y generar artículo",
        add_help=False,
    )
    parser.add_argument(
        "--model",
        type=str,
        default=Settings.AI_PROVIDER,
        choices=Settings.SUPPORTED_AI_PROVIDERS,
        help="Modelo de IA a usar",
    )
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")
    args, _ = parser.parse_known_args(sys.argv[3:])

    from src.shared.adapters.content_post_editor import post_edit_content
    from src.shared.adapters.social_post_adapter import truncate_social_post

    processor = AudioToNewsUseCase(
        debug_output_repo=create_debug_output_repository(),
        cache_dir=Settings.CACHE_DIR,
        wp_site_url=Settings.WP_SITE_URL,
        copyright_domains=Settings.VIDEO_COPYRIGHT_DOMAINS,
        download_audio=download_audio,
        transcribe_audio=transcribe_audio,
        has_audio_stream=AudioConverter().has_audio_stream,
        social_truncator=truncate_social_post,
        post_editor=post_edit_content,
        ai_providers=create_ai_providers(),
        use_ai=not args.local,
        model_provider=args.model,
    )
    result = processor.process_audio_url(url)

    logger.info(f"[AUDIO] Procesado: {url}")
    print(f"✅ Artículo: {len(result.get('article', ''))} caracteres")
    print(f"🐦 Tweet: {result.get('post', '')[:80]}...")


def main_article_from_audio():
    """Punto de entrada para generar artículo desde transcripción."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Generar artículo desde transcripción de audio"
    )
    parser.add_argument("transcript_file", help="Archivo con transcripción")
    parser.add_argument("--url", type=str, default="", help="URL del audio")
    parser.add_argument("--tema", type=str, default="Audios", help="Tema del artículo")
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")
    parser.add_argument(
        "--model",
        type=str,
        default=Settings.AI_PROVIDER,
        choices=Settings.SUPPORTED_AI_PROVIDERS,
        help="Modelo de IA a usar",
    )

    args = parser.parse_args(sys.argv[2:])

    with open(args.transcript_file, "r", encoding="utf-8") as f:
        transcript = f.read()

    from src.shared.adapters.content_post_editor import post_edit_content
    from src.shared.adapters.social_post_adapter import truncate_social_post
    from src.shared.adapters.web_search import enriquecer_con_contexto

    result = run_from_transcript(
        transcript=transcript,
        url=args.url,
        tema=args.tema,
        llm_provider=args.model,
        source_type="audio",
        ai_providers=create_ai_providers(),
        social_truncator=truncate_social_post,
        post_editor=post_edit_content,
        context_enricher=enriquecer_con_contexto,
    )

    logger.info(f"[ARTICLE_AUDIO] Artículo generado")
    print(f"✅ Título: {result['article']['title']}")
    print(
        f"📈 Estructura: {result['stats']['parrafos']}p/{result['stats']['subtitulos']}h2"
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "fetch":
            main_fetch()
        elif sys.argv[1] == "process":
            main_audio_to_news()
        elif sys.argv[1] == "article":
            main_article_from_audio()
        else:
            print(
                f"Usage: python -m src.audio.entrypoints.cli [fetch|process|article] [--model {'|'.join(Settings.SUPPORTED_AI_PROVIDERS)}] <args>"
            )
    else:
        print(
            f"Usage: python -m src.audio.entrypoints.cli [fetch|process|article] [--model {'|'.join(Settings.SUPPORTED_AI_PROVIDERS)}] <args>"
        )
