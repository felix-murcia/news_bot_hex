"""Adaptador para el servicio de Text-to-Speech (Hexagonal Architecture - Adapter)."""

import os
import time
from typing import Optional

import requests

from config.logging_config import get_logger
from src.shared.domain.ports.tts_port import TTSPort

logger = get_logger("shared.adapters.tts")


class TTSAdapter(TTSPort):
    """Adaptador que implementa el puerto TTS para el servicio Speaches."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_voice: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        from config.settings import Settings

        self.base_url = base_url or Settings.TTS_API_URL
        self.default_voice = default_voice or Settings.TTS_VOICE
        self.default_model = default_model or Settings.TTS_MODEL
        self.timeout = timeout or Settings.TTS_TIMEOUT

    def is_available(self) -> bool:
        """Verifica si el servicio TTS está disponible."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def text_to_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Convierte texto a audio usando el servicio TTS.

        Args:
            text: Texto a convertir a audio.
            voice: Voz a usar para la síntesis.
            model: Modelo TTS a utilizar.
            output_path: Ruta donde guardar el audio (opcional).

        Returns:
            Ruta del archivo de audio generado.
        """
        if not text:
            raise ValueError("El texto no puede estar vacío")

        voice = voice or self.default_voice
        model = model or self.default_model

        payload = {
            "model": model,
            "input": text,
            "voice": voice,
        }

        endpoint = f"{self.base_url}/v1/audio/speech"
        logger.info(f"[TTS] Generando audio con voz '{voice}' y modelo '{model}'")

        try:
            response = requests.post(endpoint, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[TTS] Error en la solicitud: {e}")
            raise RuntimeError(f"Error al generar audio TTS: {e}") from e

        if output_path is None:
            audio_dir = "/tmp/audios"
            os.makedirs(audio_dir, exist_ok=True)
            output_path = f"{audio_dir}/noticia_{int(time.time())}.mp3"

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

        logger.info(f"[TTS] Audio guardado en: {output_path}")
        return output_path


def text_to_speech(
    text: str,
    voice: Optional[str] = None,
    model: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """Función de conveniencia para convertir texto a audio.

    Args:
        text: Texto a convertir a audio.
        voice: Voz a usar para la síntesis.
        model: Modelo TTS a utilizar.
        output_path: Ruta donde guardar el audio (opcional).

    Returns:
        Ruta del archivo de audio generado.
    """
    adapter = TTSAdapter()
    return adapter.text_to_speech(text, voice, model, output_path)


def is_tts_available() -> bool:
    """Verifica si el servicio TTS está disponible."""
    adapter = TTSAdapter()
    return adapter.is_available()
