"""Adaptador para el servicio de Text-to-Speech (Hexagonal Architecture - Adapter)."""

import datetime
import os
import time
from pathlib import Path
from typing import Optional

import requests

from config.logging_config import get_logger
from src.shared.domain.ports.tts_port import TTSPort
from src.shared.adapters.audio_converter import AudioConverter

logger = get_logger("shared.adapters.tts")

# Instancia global del conversor de audio (para convertir WAV → MP3 si es necesario)
_audio_converter = AudioConverter()


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
            output_path: Ruta donde guardar el audio (opcional, se fuerza MP3).

        Returns:
            Ruta del archivo de audio generado (MP3).
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
            start_time = time.time()
            response = requests.post(endpoint, json=payload, timeout=self.timeout)
            elapsed_time = time.time() - start_time
            response.raise_for_status()
            logger.info(
                f"[TTS] API respondió en {elapsed_time:.2f}s - generando audio..."
            )
        except requests.RequestException as e:
            logger.error(f"[TTS] Error en la solicitud: {e}")
            raise RuntimeError(f"Error al generar audio TTS: {e}") from e

        # Determinar directorio de salida
        audio_dir = "/tmp/audios"
        os.makedirs(audio_dir, exist_ok=True)

        # Guardar audio temporal (extensión original del servicio, puede ser WAV)
        timestamp = int(time.time())
        temp_filename = f"tts_temp_{timestamp}.wav"
        temp_path = os.path.join(audio_dir, temp_filename)

        with open(temp_path, "wb") as f:
            f.write(response.content)

        temp_size = Path(temp_path).stat().st_size
        logger.info(
            f"[TTS] Audio temporal guardado: {temp_path} ({temp_size / 1024 / 1024:.2f} MB)"
        )

        # Convertir a MP3 si es WAV (o cualquier formato) para reducir tamaño
        mp3_filename = f"noticia_{timestamp}.mp3"
        if output_path:
            mp3_path = str(Path(output_path).with_suffix(".mp3"))
        else:
            mp3_path = os.path.join(audio_dir, mp3_filename)

        logger.info("[TTS] Convirtiendo a MP3 (64k)...")
        mp3_result = _audio_converter.convert_to_mp3(
            input_path=temp_path,
            output_path=mp3_path,
            bitrate="64k",
            delete_original=True,  # Eliminar temporal WAV
        )

        if mp3_result and Path(mp3_result).exists():
            mp3_size = Path(mp3_result).stat().st_size
            total_time = time.time() - start_time
            total_time_str = str(datetime.timedelta(seconds=int(total_time)))
            logger.info(
                f"[TTS] ✅ Audio MP3 guardado: {mp3_result} "
                f"({mp3_size / 1024 / 1024:.2f} MB) en {total_time_str}"
            )
            return mp3_result
        else:
            # Fallback: devolver el archivo original si la conversión falló
            logger.warning(
                f"[TTS] Conversión a MP3 falló, devolviendo archivo original: {temp_path}"
            )
            return temp_path


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
        Ruta del archivo de audio generado (MP3).
    """
    from src.shared.adapters.tts_factory import get_tts_adapter

    adapter = get_tts_adapter()
    return adapter.text_to_speech(text, voice, model, output_path)


def is_tts_available() -> bool:
    """Verifica si el servicio TTS está disponible."""
    from src.shared.adapters.tts_factory import get_tts_adapter

    adapter = get_tts_adapter()
    return adapter.is_available()
