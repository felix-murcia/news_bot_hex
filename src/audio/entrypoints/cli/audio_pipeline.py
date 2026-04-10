#!/usr/bin/env python3

"""CLI entrypoint for the unified audio pipeline.

Usage example::

    python -m src.audio.entrypoints.cli.audio_pipeline \
        --url "https://youtu.be/example" \
        --tema "tecnología" [--no-publish]
"""

import argparse
import logging
import sys

from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase

logger = logging.getLogger("audio_bot")


def parse_args(argv: list) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="audio_pipeline",
        description="Ejecuta el pipeline completo de audio → artículo → publicación",
    )
    parser.add_argument("--url", required=True, help="URL del audio a procesar")
    parser.add_argument("--tema", required=True, help="Tema o categoría del contenido")
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Ejecuta todo el pipeline pero omite la publicación en WordPress y redes",
    )
    return parser.parse_args(argv)


def main(argv: list = None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)

    logger.info("=== INICIO AUDIO PIPELINE ===")
    logger.info("[1/10] Descargando audio")
    logger.info("[2/10] Transcribiendo audio con Whisper")
    logger.info("[3/10] Generando tweets/posts")
    logger.info("[4/10] Generando artículo profesional en español (OpenRouter)")
    logger.info("[5/10] Buscando imágenes en Unsplash")
    logger.info("[6/10] Buscando imágenes en Google Images")
    logger.info("[7/10] Enriqueciendo artículo con imágenes")
    logger.info("[8/10] Publicando en WordPress")
    logger.info("[9/10] Publicando en redes sociales (Bluesky, Mastodon)")
    logger.info("[10/10] Limpiando archivos temporales")

    usecase = AudioPipelineUseCase(no_publish=args.no_publish)
    try:
        result = usecase.run(url=args.url, tema=args.tema)
    except Exception as e:
        logger.error(f"Error ejecutando el pipeline: {e}")
        sys.exit(1)

    logger.info("=== AUDIO PIPELINE COMPLETO ===")
    print(result)
    return result


if __name__ == "__main__":
    main()
