"""Módulo para convertir audio usando un servicio de conversión HTTP."""

import os
import tempfile
from typing import Optional
from pathlib import Path
from datetime import datetime

import requests
from config.logging_config import get_logger
from config.settings import Settings

logger = get_logger("news_bot.adapters.audio_converter")


class AudioConverter:
    """Convierte archivos de audio usando un servicio HTTP de ffmpeg."""

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
        self.convert_wav16k_endpoint = f"{self.base_url}/audio/convert-to-wav16k"
        self.has_audio_endpoint = f"{self.base_url}/audio/has-audio-stream"

        logger.info(
            f"[AUDIO CONVERTER] Inicializado → MP3: {self.convert_endpoint}, WAV16k: {self.convert_wav16k_endpoint}, HasAudio: {self.has_audio_endpoint}"
        )

    def convert_to_mp3(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        bitrate: str = "192k",
        delete_original: bool = False,
    ) -> Optional[str]:
        """
        Convierte un archivo de audio a MP3 usando el servicio de conversión.

        El endpoint espera: {"path": "/ruta/audio", "format": "mp3"}
        y devuelve: {"output": "/ruta/output.mp3"}

        Args:
            input_path: Ruta al archivo de audio de entrada (cualquier formato).
            output_path: Ruta de salida MP3 (si None, se genera automáticamente).
            bitrate: Bitrate del MP3 (ignorado, el servicio usa 192k fijo).
            delete_original: Si True, elimina el archivo original tras conversión exitosa.

        Returns:
            Ruta del archivo MP3 generado, o None si falla.
        """
        if not os.path.exists(input_path):
            logger.error(
                f"[AUDIO CONVERTER] Archivo de entrada no existe: {input_path}"
            )
            return None

        # Generar nombre MP3 si no se proporciona
        if not output_path:
            input_file = Path(input_path)
            output_path = str(input_file.with_suffix(".mp3"))

        logger.info(
            f"[AUDIO CONVERTER] Convirtiendo a MP3: {os.path.basename(input_path)} → {os.path.basename(output_path)}"
        )

        try:
            payload = {"path": input_path, "format": "mp3"}
            resp = requests.post(self.convert_endpoint, json=payload, timeout=300)

            if resp.status_code != 200:
                logger.error(
                    f"[AUDIO CONVERTER] Error HTTP {resp.status_code}: {resp.text[:200]}"
                )
                return None

            result = resp.json()
            converted_path = result.get("output")
            if not converted_path:
                logger.error(f"[AUDIO CONVERTER] Respuesta sin 'output': {result}")
                return None

            if not os.path.exists(converted_path):
                logger.error(
                    f"[AUDIO CONVERTER] Archivo MP3 no generado: {converted_path}"
                )
                return None

            file_size = os.path.getsize(converted_path)
            logger.info(
                f"[AUDIO CONVERTER] ✅ Conversión a MP3 exitosa: {converted_path} ({file_size / 1024 / 1024:.2f} MB)"
            )

            # Eliminar archivo original si se solicita
            if delete_original and os.path.exists(input_path):
                try:
                    os.remove(input_path)
                except Exception:
                    pass

            return converted_path

        except requests.exceptions.Timeout:
            logger.error("[AUDIO CONVERTER] Timeout después de 300s")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[AUDIO CONVERTER] No se pudo conectar al servicio: {e}")
            return None
        except Exception as e:
            logger.error(f"[AUDIO CONVERTER] Error inesperado: {e}")
            return None

    def convert_to_wav16k(
        self,
        input_path: str,
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Convierte un archivo de audio a WAV 16kHz mono usando el servicio ffmpeg.

        El endpoint espera:
        - Opción A (recomendada): JSON {"path": "/ruta/input"} → binario WAV en respuesta
        - Opción B (legacy): multipart/form-data con campo 'file' (límite 25 MB)

        Args:
            input_path: Ruta al archivo de audio de entrada (cualquier formato).
            output_path: Ruta de salida WAV (si None, se genera automáticamente).

        Returns:
            Ruta del archivo WAV generado, o None si falla.
        """
        if not os.path.exists(input_path):
            logger.error(
                f"[AUDIO CONVERTER] Archivo de entrada no existe: {input_path}"
            )
            return None

        # Generar nombre de salida si no se proporciona
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_path = str(Path(tempfile.gettempdir()) / f"wav16k_{timestamp}.wav")

        logger.info(
            f"[AUDIO CONVERTER] Convirtiendo a WAV16k: {os.path.basename(input_path)} → {os.path.basename(output_path)}"
        )

        try:
            # Enviar ruta como JSON (evita límite 25 MB, archivo debe estar accesible en servidor)
            payload = {"path": input_path}
            resp = requests.post(
                self.convert_wav16k_endpoint,
                json=payload,
                timeout=300,
            )

            if resp.status_code != 200:
                logger.error(
                    f"[AUDIO CONVERTER] Error HTTP {resp.status_code}: {resp.text[:200]}"
                )
                return None

            # Respuesta es binaria (audio/wav), no JSON
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)
            with open(output_path, "wb") as out_f:
                out_f.write(resp.content)

            file_size = os.path.getsize(output_path)
            logger.info(
                f"[AUDIO CONVERTER] ✅ Conversión a WAV16k exitosa: {output_path} ({file_size / 1024 / 1024:.2f} MB)"
            )

            return output_path

        except requests.exceptions.Timeout:
            logger.error("[AUDIO CONVERTER] Timeout después de 300s")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[AUDIO CONVERTER] No se pudo conectar al servicio: {e}")
            return None
        except Exception as e:
            logger.error(f"[AUDIO CONVERTER] Error inesperado: {e}")
            return None

        # Generar nombre de salida si no se proporciona
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_path = str(Path(tempfile.gettempdir()) / f"wav16k_{timestamp}.wav")

        logger.info(
            f"[AUDIO CONVERTER] Convirtiendo a WAV16k: {os.path.basename(input_path)} → {os.path.basename(output_path)}"
        )

        try:
            # Enviar archivo como multipart/form-data ( Campo 'file' )
            with open(input_path, "rb") as f:
                files = {
                    "file": (
                        os.path.basename(input_path),
                        f,
                        "application/octet-stream",
                    )
                }
                resp = requests.post(
                    self.convert_wav16k_endpoint,
                    files=files,
                    timeout=300,
                )

            if resp.status_code != 200:
                logger.error(
                    f"[AUDIO CONVERTER] Error HTTP {resp.status_code}: {resp.text[:200]}"
                )
                return None

            # Respuesta es binaria (audio/wav), no JSON
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)
            with open(output_path, "wb") as out_f:
                out_f.write(resp.content)

            file_size = os.path.getsize(output_path)
            logger.info(
                f"[AUDIO CONVERTER] ✅ Conversión a WAV16k exitosa: {output_path} ({file_size / 1024 / 1024:.2f} MB)"
            )

            return output_path

        except requests.exceptions.Timeout:
            logger.error("[AUDIO CONVERTER] Timeout después de 300s")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[AUDIO CONVERTER] No se pudo conectar al servicio: {e}")
            return None
        except Exception as e:
            logger.error(f"[AUDIO CONVERTER] Error inesperado: {e}")
            return None

    def has_audio_stream(self, file_path: str) -> bool:
        """
        Verifica si un archivo contiene un stream de audio usando el servicio ffmpeg.

        El endpoint espera: {"path": "/ruta/archivo"} y devuelve: {"has_audio": true/false}

        Args:
            file_path: Ruta al archivo de video/audio.

        Returns:
            True si tiene stream de audio, False en caso contrario.
        """
        if not os.path.exists(file_path):
            logger.error(f"[AUDIO CONVERTER] Archivo no existe: {file_path}")
            return False

        try:
            payload = {"path": file_path}
            resp = requests.post(
                self.has_audio_endpoint,
                json=payload,
                timeout=30,
            )

            if resp.status_code != 200:
                logger.error(
                    f"[AUDIO CONVERTER] Error HTTP {resp.status_code}: {resp.text[:200]}"
                )
                return False

            result = resp.json()
            has_audio = result.get("has_audio", False)
            return bool(has_audio)

        except requests.exceptions.Timeout:
            logger.error("[AUDIO CONVERTER] Timeout verificando audio stream")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[AUDIO CONVERTER] No se pudo conectar al servicio: {e}")
            return False
        except Exception as e:
            logger.error(f"[AUDIO CONVERTER] Error inesperado: {e}")
            return False
