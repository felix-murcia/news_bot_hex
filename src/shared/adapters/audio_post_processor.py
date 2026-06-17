"""Audio post-processor for cleaning and stabilizing TTS synthesis artifacts.

Uses ffmpeg-api service for audio processing instead of direct subprocess calls.
Addresses Coqui TTS issues like spectral artifacts, plosives, and breathing sounds
through normalization, filtering, and audio restoration techniques.
"""

import os
import requests
from pathlib import Path
from typing import Optional

from config.logging_config import get_logger
from config.settings import Settings
from src.shared.adapters.audio_converter_factory import get_audio_converter_url
from src.shared.domain.ports.audio_post_processor_port import AudioPostProcessorPort

logger = get_logger("news_bot.adapters.audio_post_processor")


class AudioPostProcessor(AudioPostProcessorPort):
    """Post-process TTS audio using ffmpeg-api service."""

    def __init__(self, base_url: str = None):
        """
        Initialize the post-processor.

        Args:
            base_url: URL base of ffmpeg-api service (e.g., http://localhost:8082)
        """
        self.base_url = (base_url or get_audio_converter_url()).rstrip("/")
        self.post_process_endpoint = f"{self.base_url}/audio/post-process"
        logger.info(f"[AUDIO POST] Inicializado → endpoint: {self.post_process_endpoint}")

    def process(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        normalize: bool = True,
        remove_breathing: bool = True,
        stabilize_plosives: bool = True,
        noise_gate_threshold: float = -40.0,
    ) -> Optional[str]:
        """
        Post-process audio to remove TTS artifacts.

        Args:
            input_path: Path to input audio file
            output_path: Path for output file (if None, overwrites input)
            normalize: Apply loudness normalization
            remove_breathing: Apply breathing sound reduction
            stabilize_plosives: Apply plosive/artifact stabilization
            noise_gate_threshold: Threshold in dB for noise gate

        Returns:
            Path to processed audio or None if processing failed
        """
        if not os.path.exists(input_path):
            logger.error(f"[AUDIO POST] Input file not found: {input_path}")
            return None

        output_path = output_path or input_path

        logger.info("[AUDIO POST] Iniciando post-procesamiento de audio...")

        try:
            payload = {
                "path": input_path,
                "normalize": normalize,
                "remove_breathing": remove_breathing,
                "stabilize_plosives": stabilize_plosives,
                "noise_gate_threshold": noise_gate_threshold,
            }

            resp = requests.post(self.post_process_endpoint, json=payload, timeout=300)

            if resp.status_code != 200:
                logger.error(
                    f"[AUDIO POST] Error HTTP {resp.status_code}: {resp.text[:200]}"
                )
                return None

            # Response is binary audio data
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(resp.content)

            file_size = os.path.getsize(output_path)
            logger.info(
                f"[AUDIO POST] ✅ Audio post-procesado: {output_path} ({file_size / 1024 / 1024:.2f} MB)"
            )

            return output_path

        except requests.exceptions.Timeout:
            logger.error("[AUDIO POST] Timeout después de 300s")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[AUDIO POST] No se pudo conectar al servicio: {e}")
            return None
        except Exception as e:
            logger.error(f"[AUDIO POST] Error inesperado: {e}")
            return None


def post_process_audio(
    input_path: str,
    output_path: Optional[str] = None,
    aggressive: bool = False,
) -> Optional[str]:
    """
    Convenience function to post-process audio using ffmpeg-api.

    Args:
        input_path: Path to input audio file
        output_path: Path for output file
        aggressive: Use aggressive settings for heavily distorted audio

    Returns:
        Path to processed audio or None if failed
    """
    processor = AudioPostProcessor(base_url=get_audio_converter_url())

    # Adjust parameters based on aggressiveness
    noise_gate = -35.0 if aggressive else -40.0

    return processor.process(
        input_path=input_path,
        output_path=output_path,
        normalize=True,
        remove_breathing=True,
        stabilize_plosives=True,
        noise_gate_threshold=noise_gate,
    )
