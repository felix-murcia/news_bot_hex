"""Fábrica para crear instancias de AudioConverter (Hexagonal Architecture - Factory)."""

from src.shared.adapters.audio_converter import AudioConverter
from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot.adapters.audio_converter_factory")

_converter_cache: dict[str, AudioConverter] = {}


def get_audio_converter_url(mode: str = None) -> str:
    """Retorna la URL del servicio de audio según el modo configurado."""
    if mode is None:
        mode = Settings.AUDIO_CONVERTER_MODE.lower()
    if mode == "external":
        return Settings.AUDIO_CONVERTER_EXTERNAL_URL
    return Settings.FFMPEG_API_URL


def get_audio_converter(mode: str = None) -> AudioConverter:
    """
    Retorna un AudioConverter configurado según el modo.

    Args:
        mode: "local" usa FFMPEG_API_URL, "external" usa AUDIO_CONVERTER_EXTERNAL_URL.
              Si es None, usa Settings.AUDIO_CONVERTER_MODE.
    """
    if mode is None:
        mode = Settings.AUDIO_CONVERTER_MODE.lower()

    if mode in _converter_cache:
        return _converter_cache[mode]

    if mode == "external":
        url = Settings.AUDIO_CONVERTER_EXTERNAL_URL
        logger.info(f"[AUDIO CONVERTER FACTORY] Modo externo → {url}")
    elif mode == "local":
        url = Settings.FFMPEG_API_URL
        logger.info(f"[AUDIO CONVERTER FACTORY] Modo local → {url}")
    else:
        logger.error(f"[AUDIO CONVERTER FACTORY] Modo no válido: '{mode}'. Usando 'local' como fallback.")
        url = Settings.FFMPEG_API_URL
        mode = "local"

    converter = AudioConverter(base_url=url)
    _converter_cache[mode] = converter
    return converter
