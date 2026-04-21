"""Módulo para convertir audio WAV a MP3 usando un servicio de conversión HTTP."""

import os
from typing import Optional
from pathlib import Path

import requests
from config.logging_config import get_logger
from config.settings import Settings

logger = get_logger("news_bot.adapters.audio_converter")


class AudioConverter:
    """Convierte archivos de audio WAV a MP3 usando un servicio HTTP de ffmpeg."""

    def __init__(self, base_url: str = None):
        """
        Inicializa el conversor.

        Args:
            base_url: URL base del servicio de conversión (ej: http://localhost:8082).
                     Si es None, usa Settings.FFMPEG_API_URL.
        """
        self.base_url = base_url or Settings.FFMPEG_API_URL
        self.base_url = self.base_url.rstrip("/")
        self.convert_endpoint = f"{self.base_url}/audio/convert-by-path"

        logger.info(
            f"[AUDIO CONVERTER] Inicializado → endpoint: {self.convert_endpoint}"
        )

    def convert_wav_to_mp3(
        self,
        wav_path: str,
        mp3_path: Optional[str] = None,
        bitrate: str = "192k",
        delete_original: bool = False,
    ) -> Optional[str]:
        """
        Convierte un archivo WAV a MP3 usando el servicio de conversión.

        El endpoint espera: {"path": "/ruta/wav", "format": "mp3"}
        y devuelve: {"output": "/ruta/output.mp3"}

        Args:
            wav_path: Ruta al archivo WAV de entrada.
            mp3_path: Ruta de salida MP3 (si None, se genera automáticamente).
            bitrate: Bitrate del MP3 (ignorado, el servicio usa 192k fijo).
            delete_original: Si True, elimina el WAV tras conversión exitosa.

        Returns:
            Ruta del archivo MP3 generado, o None si falla.
        """
        if not os.path.exists(wav_path):
            logger.error(f"[AUDIO CONVERTER] Archivo WAV no existe: {wav_path}")
            return None

        # Generar nombre MP3 si no se proporciona
        if not mp3_path:
            wav_file = Path(wav_path)
            mp3_path = str(wav_file.with_suffix(".mp3"))

        logger.info(
            f"[AUDIO CONVERTER] Convirtiendo: {os.path.basename(wav_path)} → {os.path.basename(mp3_path)}"
        )

        try:
            # Enviar JSON al endpoint: {"path": "...", "format": "mp3"}
            payload = {
                "path": wav_path,
                "format": "mp3",
            }

            resp = requests.post(
                self.convert_endpoint,
                json=payload,
                timeout=300,
            )

            if resp.status_code != 200:
                logger.error(
                    f"[AUDIO CONVERTER] Error HTTP {resp.status_code}: {resp.text[:200]}"
                )
                return None

            # Leer respuesta JSON: {"output": "/ruta/output.mp3"}
            try:
                result = resp.json()
                converted_path = result.get("output")
                if not converted_path:
                    logger.error(f"[AUDIO CONVERTER] Respuesta sin 'output': {result}")
                    return None
            except Exception as e:
                logger.error(f"[AUDIO CONVERTER] No se pudo parsear JSON: {e}")
                return None

            # Verificar que el archivo exista
            if not os.path.exists(converted_path):
                logger.error(
                    f"[AUDIO CONVERTER] Archivo MP3 no generado: {converted_path}"
                )
                return None

            file_size = os.path.getsize(converted_path)
            logger.info(
                f"[AUDIO CONVERTER] ✅ Conversión exitosa: {converted_path} ({file_size / 1024 / 1024:.2f} MB)"
            )

            # El endpoint ya elimina el WAV, pero por si acaso
            if delete_original and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

            return converted_path

        except requests.exceptions.Timeout:
            logger.error(f"[AUDIO CONVERTER] Timeout después de 300s")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[AUDIO CONVERTER] No se pudo conectar al servicio: {e}")
            return None
        except Exception as e:
            logger.error(f"[AUDIO CONVERTER] Error inesperado: {e}")
            return None
