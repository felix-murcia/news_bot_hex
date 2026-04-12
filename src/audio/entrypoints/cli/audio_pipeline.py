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
import time

from config.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger("audio_bot.pipeline")

from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase


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

    pipeline_start = time.time()
    logger.info("=" * 60)
    logger.info("AUDIO PIPELINE — INICIO")
    logger.info(f"URL: {args.url}")
    logger.info(f"Tema: {args.tema}")
    logger.info(f"Publish: {not args.no_publish}")
    logger.info("=" * 60)

    usecase = AudioPipelineUseCase(no_publish=args.no_publish)
    try:
        result = usecase.run(url=args.url, tema=args.tema)
    except Exception as e:
        elapsed = time.time() - pipeline_start
        logger.error(f"AUDIO PIPELINE — Error tras {elapsed:.1f}s: {e}", exc_info=True)
        sys.exit(1)

    elapsed = time.time() - pipeline_start
    logger.info("=" * 60)
    logger.info(f"AUDIO PIPELINE — FINALIZADO en {elapsed:.1f}s")
    logger.info(f"WordPress URL: {result.get('wordpress_url', 'N/A')}")
    logger.info(f"Social platforms: {len(result.get('social_results', []))}")
    logger.info("=" * 60)
    return result


if __name__ == "__main__":
    main()
