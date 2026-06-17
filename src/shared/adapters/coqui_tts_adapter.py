"""Adaptador para Coqui TTS (Hexagonal Architecture - Adapter)."""

import os
import requests
from typing import Optional
from pathlib import Path
from datetime import datetime

from src.shared.domain.ports.tts_port import TTSPort
from src.shared.adapters.audio_converter_factory import get_audio_converter
from src.shared.adapters.tts_text_processor import TTSTextProcessor
from src.shared.adapters.audio_post_processor import post_process_audio
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
        language: str = None,
        speed: float = None,
        timeout: int = None,
        temperature: float = None,
        enable_post_processing: bool = None,
    ):
        from config.settings import Settings

        self.api_url = api_url or Settings.COQUI_API_URL
        self.voice = voice or Settings.COQUI_VOICE
        self.model = model or Settings.COQUI_MODEL
        self.language = language or Settings.COQUI_LANGUAGE
        self.speed = speed if speed is not None else float(Settings.COQUI_SPEED)
        self.atempo = float(Settings.COQUI_ATEMPO)
        # TTS_TIMEOUT está en milisegundos (convención del proyecto); requests lo espera en segundos
        raw_ms = timeout or int(Settings.TTS_TIMEOUT)
        self.timeout = raw_ms / 1000

        # Stability parameters for artifact reduction
        self.temperature = (
            temperature if temperature is not None
            else float(getattr(Settings, "COQUI_TEMPERATURE", "0.85"))
        )
        self.enable_post_processing = (
            enable_post_processing if enable_post_processing is not None
            else getattr(Settings, "COQUI_POST_PROCESSING", True)
        )

        # Asegurar directorio de audios
        self.audio_dir = Path("/tmp/audios")
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        # Inicializar conversor a MP3
        self.converter = get_audio_converter()

        logger.info(
            f"[COQUI TTS] Adaptador inicializado → API: {self.api_url}, voice: {self.voice}, "
            f"temperature: {self.temperature}, post_processing: {self.enable_post_processing}"
        )

    def _apply_atempo_filter(self, wav_path: str) -> Optional[str]:
        """
        Apply atempo filter to adjust audio speed using ffmpeg-api.

        Args:
            wav_path: Path to input WAV file

        Returns:
            Path to tempo-adjusted WAV file, or None if failed
        """
        try:
            payload = {
                "path": wav_path,
                "tempo_factor": self.atempo,
            }

            atempo_endpoint = f"{self.converter.base_url}/audio/apply-atempo"
            resp = requests.post(atempo_endpoint, json=payload, timeout=300)

            if resp.status_code != 200:
                logger.error(
                    f"[COQUI TTS] Error aplicando atempo (HTTP {resp.status_code}): {resp.text[:200]}"
                )
                return None

            # Response is binary audio data, save to temp file
            atempo_wav_path = str(Path(wav_path).with_suffix(".atempo.wav"))
            with open(atempo_wav_path, "wb") as f:
                f.write(resp.content)

            return atempo_wav_path

        except requests.exceptions.Timeout:
            logger.error("[COQUI TTS] Timeout aplicando atempo")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[COQUI TTS] No se pudo conectar al servicio atempo: {e}")
            return None
        except Exception as e:
            logger.error(f"[COQUI TTS] Error aplicando atempo: {e}")
            return None

    def is_available(self) -> bool:
        """Verifica si el servicio Coqui TTS está disponible."""
        return True

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

        # Procesar texto para evitar artefactos de síntesis
        original_text = text
        text = TTSTextProcessor.process(text)
        if text != original_text:
            logger.debug(f"[COQUI TTS] Texto procesado")
            logger.debug(f"[COQUI TTS] Original: {original_text[:100]}...")
            logger.debug(f"[COQUI TTS] Procesado: {text[:100]}...")

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
        if self.language:
            params["language"] = self.language
        params["temperature"] = self.temperature

        request_url = f"{self.api_url}/api/tts"
        logger.info(
            f"[COQUI TTS] Solicitud: GET /api/tts → model: {self.model}, speed: {self.speed}, "
            f"temperature: {self.temperature}"
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

            # Aplicar filtro atempo si es necesario
            if self.atempo != 1.0:
                logger.info(f"[COQUI TTS] Aplicando filtro atempo: {self.atempo}x")
                atempo_wav_path = self._apply_atempo_filter(wav_path)
                if atempo_wav_path:
                    # Eliminar el WAV original
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass
                    wav_path = atempo_wav_path
                    logger.info(f"[COQUI TTS] ✅ Filtro atempo aplicado: {self.atempo}x")
                else:
                    logger.warning("[COQUI TTS] Continuando sin aplicar atempo")

            wav_size = Path(wav_path).stat().st_size
            logger.info(
                f"[COQUI TTS] ✅ WAV generado: {wav_path} ({wav_size / 1024 / 1024:.2f} MB)"
            )

            # Post-process audio to remove TTS artifacts
            if self.enable_post_processing:
                logger.info("[COQUI TTS] Aplicando post-procesamiento de audio...")
                processed_wav = post_process_audio(
                    input_path=wav_path,
                    output_path=None,
                    aggressive=False,
                )
                if processed_wav and os.path.exists(processed_wav):
                    wav_path = processed_wav
                    wav_size = Path(wav_path).stat().st_size
                    logger.info(
                        f"[COQUI TTS] ✅ Audio post-procesado: {wav_path} "
                        f"({wav_size / 1024 / 1024:.2f} MB)"
                    )
                else:
                    logger.warning(
                        "[COQUI TTS] Post-procesamiento falló, continuando con audio original"
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
