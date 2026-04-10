import os
import logging
from typing import Optional
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("video_bot")

IS_JETSON = os.path.exists("/etc/nv_tegra_release")
if IS_JETSON:
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"


def has_audio_stream(video_path: str) -> bool:
    """Check if video has an audio stream."""
    try:
        import subprocess

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                video_path,
            ],
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())
    except Exception:
        return True


def transcribe_video(video_path: str) -> str:
    """Transcribe un video usando Whisper."""
    logger.info(
        f"[TRANSCRIBER] Iniciando transcripción: {os.path.basename(video_path)}"
    )

    try:
        import whisper
        import numpy as np

        model = whisper.load_model("medium", device="cpu")
        logger.info("[TRANSCRIBER] Modelo cargado")

        result = model.transcribe(
            video_path, language=None, task="transcribe", verbose=False, fp16=False
        )

        text = result["text"].strip()
        detected_lang = result.get("language", "desconocido")

        logger.info(f"[TRANSCRIBER] Idioma: {detected_lang}")
        logger.info(f"[TRANSCRIBER] Transcripción: {len(text)} caracteres")

        if not text or len(text) < 50:
            logger.warning(f"[TRANSCRIBER] Transcripción muy corta")

        return text

    except ImportError:
        logger.error("[TRANSCRIBER] Whisper no instalado")
        raise RuntimeError("Instala whisper: pip install openai-whisper")
    except Exception as e:
        logger.error(f"[TRANSCRIBER] Error: {e}")
        raise


class VideoTranscriber:
    """Transcriptor de videos."""

    def __init__(self, model_size: str = "tiny"):
        self.model_size = model_size
        self._model = None

    @property
    def model(self):
        if self._model is None:
            import whisper

            self._model = whisper.load_model(self.model_size, device="cpu")
        return self._model

    def transcribe(self, video_path: str) -> str:
        """Transcribe un video."""
        result = self.model.transcribe(video_path, language=None, task="transcribe")
        return result["text"].strip()


def run(video_path: str) -> str:
    """Función principal."""
    return transcribe_video(video_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = transcribe_video(sys.argv[1])
        print(f"✅ {len(result)} caracteres")
    else:
        print("Usage: python video_transcriber.py <video_file>")
