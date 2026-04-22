"""Adaptador para Coqui TTS (Hexagonal Architecture - Adapter)."""

import os
import requests
from typing import Optional
from pathlib import Path
from datetime import datetime

from src.shared.domain.ports.tts_port import TTSPort
from src.shared.adapters.audio_converter import AudioConverter
from config.logging_config import get_logger

logger = get_logger("news_bot.adapters.coqui_tts")


class CoquiTTSAdapter(TTSPort):
    """
    Adaptador para Coqui TTS Server.

    Usa la API HTTP de Coqui TTS (ej: http://localhost:5002/api/tts).
    El texto se codifica en URL para la petición.
    Devuelve archivos WAV en /tmp/audios/.
    """

    def __init__(
        self,
        api_url: str = None,
        voice: str = None,
        model: str = None,
        timeout: int = None,
    ):
        from config.settings import Settings

        self.api_url = api_url or Settings.COQUI_API_URL
        self.voice = voice or Settings.COQUI_VOICE
        self.model = model or Settings.COQUI_MODEL
        self.timeout = timeout or Settings.TTS_TIMEOUT

        # Asegurar directorio de audios
        self.audio_dir = Path("/tmp/audios")
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        # Inicializar conversor a MP3
        self.converter = AudioConverter()

        logger.info(
            f"[COQUI TTS] Adaptador inicializado → API: {self.api_url}, voice: {self.voice}"
        )

    def is_available(self) -> bool:
        """Verifica si el servicio Coqui TTS está disponible."""
        try:
            # Prueba el endpoint real con un texto corto
            test_url = f"{self.api_url}/api/tts"
            params = {"text": "test"}
            if self.voice:
                params["voice"] = self.voice
            resp = requests.get(test_url, params=params, timeout=5, stream=True)
            if resp.status_code == 200:
                resp.close()  # No descargar contenido
                logger.info("[COQUI TTS] Servicio disponible")
                return True
        except Exception as e:
            logger.warning(f"[COQUI TTS] Servicio no disponible: {e}")
        return False

    def text_to_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Convierte texto a audio usando Coqui TTS API y convierte a MP3.

        Args:
            text: Texto a convertir.
            voice: IGNORADO - Coqui usa la voice configurada en __init__.
            model: IGNORADO - Parámetro por compatibilidad con TTSPort.
            output_path: Ruta personalizada de salida (opcional, se fuerza MP3).

        Returns:
            Ruta absoluta del archivo MP3 generado.
        """
        if not text or not text.strip():
            logger.error("[COQUI TTS] Texto vacío")
            return ""

        # Determinar ruta de salida WAV (temporal)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        wav_filename = f"noticia_{timestamp}.wav"
        wav_path = str(self.audio_dir / wav_filename)

        # Si el usuario especificó output_path, forzar extensión .mp3
        if output_path:
            mp3_path = str(Path(output_path).with_suffix(".mp3"))
        else:
            mp3_filename = f"noticia_{timestamp}.mp3"
            mp3_path = str(self.audio_dir / mp3_filename)

        # Construir parámetros de la petición
        params = {"text": text}
        if self.voice:
            params["voice"] = self.voice

        request_url = f"{self.api_url}/api/tts"
        logger.info(
            f"[COQUI TTS] Solicitud: GET /api/tts (voice={self.voice[:30] if self.voice else 'default'}...)"
        )
        logger.debug(f"[COQUI TTS] Texto original: {text[:80]}...")

        try:
            resp = requests.get(
                request_url, params=params, timeout=self.timeout, stream=True
            )

            if resp.status_code != 200:
                error_msg = (
                    f"[COQUI TTS] Error HTTP {resp.status_code}: {resp.text[:200]}"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            # Guardar audio WAV temporal
            with open(wav_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            wav_size = Path(wav_path).stat().st_size
            logger.info(
                f"[COQUI TTS] ✅ WAV generado: {wav_path} ({wav_size / 1024 / 1024:.2f} MB)"
            )

            # Convertir WAV a MP3
            logger.info("[COQUI TTS] Iniciando conversión a MP3...")
            mp3_result = self.converter.convert_to_mp3(
                input_path=wav_path,
                output_path=mp3_path,
                delete_original=True,  # Eliminar WAV tras conversión exitosa
            )

            if mp3_result and os.path.exists(mp3_result):
                mp3_size = os.path.getsize(mp3_result)
                logger.info(
                    f"[COQUI TTS] ✅ MP3 generado: {mp3_result} ({mp3_size / 1024 / 1024:.2f} MB)"
                )
                return mp3_result
            else:
                logger.warning(
                    f"[COQUI TTS] Conversión a MP3 falló, devolviendo WAV: {wav_path}"
                )
                return wav_path

        except requests.exceptions.Timeout as e:
            logger.error(f"[COQUI TTS] Timeout después de {self.timeout}s")
            raise RuntimeError(f"Coqui TTS timeout: {e}") from e
        except Exception as e:
            logger.error(f"[COQUI TTS] Error: {e}")
            raise RuntimeError(f"Coqui TTS error: {e}") from e
