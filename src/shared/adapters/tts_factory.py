"""Fábrica para crear adaptadores TTS (Hexagonal Architecture - Factory)."""

from typing import Optional

from src.shared.domain.ports.tts_port import TTSPort
from src.shared.adapters.tts_adapter import TTSAdapter
from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter
from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot.adapters.tts_factory")

# Cache del adaptador (singleton por modo)
_adapter_cache = {}


def get_tts_adapter(mode: str = None) -> TTSPort:
    """
    Crea y retorna el adaptador TTS según el modo configurado.

    Usa caché para retornar la misma instancia en llamadas sucesivas.

    Args:
        mode: Modo TTS ("speaches" o "coqui"). Si es None, usa Settings.TTS_MODE.

    Returns:
        Instancia del adaptador TTS solicitado.

    Raises:
        ValueError: Si el modo no es reconocido.
    """
    if mode is None:
        mode = Settings.TTS_MODE.lower()

    # Retornar desde caché si existe
    if mode in _adapter_cache:
        logger.debug(f"[TTS FACTORY] Adaptador '{mode}' recuperado de caché")
        return _adapter_cache[mode]

    logger.info(f"[TTS FACTORY] Creando nuevo adaptador TTS en modo: {mode}")

    if mode == "speaches":
        adapter = TTSAdapter()
        logger.info("[TTS FACTORY] ✅ Adaptador Speaches (Kokoro) instanciado")
    elif mode == "coqui":
        adapter = CoquiTTSAdapter()
        logger.info("[TTS FACTORY] ✅ Adaptador Coqui TTS instanciado")
    else:
        logger.error(
            f"[TTS FACTORY] Modo TTS no válido: '{mode}'. Usando 'speaches' como fallback."
        )
        adapter = TTSAdapter()
        mode = "speaches"  # normalizar clave

    # Guardar en caché
    _adapter_cache[mode] = adapter
    return adapter
