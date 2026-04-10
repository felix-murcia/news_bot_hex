import os
import logging
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("audio_bot")

IS_JETSON = os.path.exists("/etc/nv_tegra_release")
if IS_JETSON:
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"


def transcribe_audio(audio_path: str) -> str:
    """Transcribe un audio usando Whisper."""
    logger.info(
        f"[TRANSCRIBER] Iniciando transcripción: {os.path.basename(audio_path)}"
    )

    try:
        import whisper
        import numpy as np

        model = whisper.load_model("medium", device="cpu")
        logger.info("[TRANSCRIBER] Modelo cargado")

        result = model.transcribe(
            audio_path, language=None, task="transcribe", verbose=False, fp16=False
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


class AudioTranscriber:
    """Transcriptor de audios."""

    def __init__(self, model_size: str = "tiny"):
        self.model_size = model_size
        self._model = None

    @property
    def model(self):
        if self._model is None:
            import whisper

            self._model = whisper.load_model(self.model_size, device="cpu")
        return self._model

    def transcribe(self, audio_path: str) -> str:
        """Transcribe un audio."""
        result = self.model.transcribe(audio_path, language=None, task="transcribe")
        return result["text"].strip()


def run(audio_path: str) -> str:
    """Función principal."""
    return transcribe_audio(audio_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = transcribe_audio(sys.argv[1])
        print(f"✅ {len(result)} caracteres")
    else:
        print("Usage: python audio_transcriber.py <audio_file>")
