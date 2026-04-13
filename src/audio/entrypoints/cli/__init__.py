from config.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger("audio_bot")
from src.audio.infrastructure.adapters.audio_fetcher import AudioFetcher, download_audio
from src.audio.application.usecases.audio_to_news import process_audio_url
from src.shared.application.usecases.article_from_transcript import run_from_transcript
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
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m src.audio.entrypoints.cli process <audio_url>")
        return

    url = sys.argv[2]
    result = process_audio_url(url)

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

    result = run_from_transcript(
        transcript=transcript,
        url=args.url,
        tema=args.tema,
        llm_provider=args.model,
        source_type="audio",
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
