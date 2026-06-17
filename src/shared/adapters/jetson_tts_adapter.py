"""Adaptador para TTS server en Jetson (OpenAI-compatible /v1/audio/speech)."""

import datetime
import os
import time
from pathlib import Path
from typing import Optional

import requests

from config.logging_config import get_logger
from src.shared.domain.ports.tts_port import TTSPort
from src.shared.adapters.audio_converter_factory import get_audio_converter

logger = get_logger("news_bot.adapters.jetson_tts")

_audio_converter = get_audio_converter()


class JetsonTTSAdapter(TTSPort):
    """Adaptador para el servidor TTS en Jetson via API OpenAI-compatible."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_voice: Optional[str] = None,
        default_language: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        from config.settings import Settings

        self.base_url = (base_url or Settings.JETSON_TTS_API_URL).rstrip("/")
        self.default_voice = default_voice or Settings.JETSON_TTS_VOICE
        self.default_language = default_language or Settings.JETSON_TTS_LANGUAGE
        raw_ms = timeout or int(Settings.TTS_TIMEOUT)
        self.timeout = raw_ms / 1000

        logger.info(
            f"[JETSON TTS] Adaptador inicializado → API: {self.base_url}, "
            f"voice: {self.default_voice}, language: {self.default_language}"
        )

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def text_to_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,  # ignorado, la API Jetson no usa model
        output_path: Optional[str] = None,
    ) -> str:
        if not text or not text.strip():
            raise ValueError("El texto no puede estar vacío")

        voice = voice or self.default_voice

        payload = {
            "input": text,
            "voice": voice,
            "language": self.default_language,
        }

        endpoint = f"{self.base_url}/v1/audio/speech"
        logger.info(f"[JETSON TTS] Generando audio → voz: '{voice}', language: '{self.default_language}'")

        audio_dir = "/tmp/audios"
        os.makedirs(audio_dir, exist_ok=True)

        try:
            start_time = time.time()
            response = requests.post(endpoint, json=payload, timeout=self.timeout)
            elapsed = time.time() - start_time
            response.raise_for_status()
            logger.info(f"[JETSON TTS] API respondió en {elapsed:.2f}s")
        except requests.exceptions.Timeout:
            logger.error(f"[JETSON TTS] Timeout después de {self.timeout}s")
            raise RuntimeError(f"Jetson TTS timeout tras {self.timeout}s")
        except requests.RequestException as e:
            logger.error(f"[JETSON TTS] Error de conexión: {e}")
            raise RuntimeError(f"Error al generar audio en Jetson TTS: {e}") from e

        timestamp = int(time.time())
        temp_path = os.path.join(audio_dir, f"jetson_tts_temp_{timestamp}.wav")

        with open(temp_path, "wb") as f:
            f.write(response.content)

        temp_size = Path(temp_path).stat().st_size
        logger.info(f"[JETSON TTS] Audio temporal: {temp_path} ({temp_size / 1024 / 1024:.2f} MB)")

        if output_path:
            mp3_path = str(Path(output_path).with_suffix(".mp3"))
        else:
            mp3_path = os.path.join(audio_dir, f"noticia_{timestamp}.mp3")

        mp3_result = _audio_converter.convert_to_mp3(
            input_path=temp_path,
            output_path=mp3_path,
            bitrate="64k",
            delete_original=True,
        )

        if mp3_result and Path(mp3_result).exists():
            mp3_size = Path(mp3_result).stat().st_size
            total = time.time() - start_time
            logger.info(
                f"[JETSON TTS] ✅ MP3 generado: {mp3_result} "
                f"({mp3_size / 1024 / 1024:.2f} MB) en {str(datetime.timedelta(seconds=int(total)))}"
            )
            return mp3_result
        else:
            logger.warning(f"[JETSON TTS] Conversión a MP3 falló, devolviendo: {temp_path}")
            return temp_path
