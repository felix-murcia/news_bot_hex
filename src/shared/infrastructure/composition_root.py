"""
Composition Root — Punto único de creación de dependencias.

Este módulo centraliza la instanciación de TODOS los adaptadores.
Es usado por dependencies.py (API/FastAPI) y por CLI.
No contiene lógica de negocio. Solo crea y conecta objetos.
"""

from src.shared.domain.ports.audio_converter_port import AudioConverterPort
from src.shared.domain.ports.audio_post_processor_port import AudioPostProcessorPort
from src.shared.domain.ports.tts_port import TTSPort
from src.shared.domain.ports.ai_model_port import AIModelPort
from src.shared.domain.ports.video_generator_port import VideoGeneratorPort
from src.audio.domain.ports.audio_fetcher_port import AudioFetcherPort
from src.audio.domain.ports.audio_transcriber_port import AudioTranscriberPort
from src.video.domain.ports.video_fetcher_port import VideoFetcherPort
from src.video.domain.ports.video_transcriber_port import VideoTranscriberPort


def create_audio_converter() -> AudioConverterPort:
    from src.shared.adapters.audio_converter_factory import get_audio_converter
    return get_audio_converter()


def create_audio_post_processor() -> AudioPostProcessorPort:
    from src.shared.adapters.audio_post_processor import AudioPostProcessor
    return AudioPostProcessor()


def create_tts_adapter() -> TTSPort:
    from src.shared.adapters.tts_factory import get_tts_adapter
    return get_tts_adapter()


def create_ai_adapter(provider: str = None) -> AIModelPort:
    from src.shared.adapters.ai.ai_factory import get_ai_adapter
    return get_ai_adapter(provider=provider)


def create_video_generator() -> VideoGeneratorPort:
    from src.shared.adapters.video_generator import get_video_generator
    return get_video_generator()


def create_audio_fetcher() -> AudioFetcherPort:
    from src.audio.infrastructure.adapters.audio_fetcher import AudioFetcher
    return AudioFetcher()


def create_audio_transcriber() -> AudioTranscriberPort:
    from src.audio.infrastructure.adapters.audio_transcriber import AudioTranscriber
    return AudioTranscriber()


def create_video_fetcher() -> VideoFetcherPort:
    from src.video.infrastructure.adapters.video_fetcher import VideoFetcher
    return VideoFetcher()


def create_video_transcriber() -> VideoTranscriberPort:
    from src.video.infrastructure.adapters.video_transcriber import VideoTranscriber
    return VideoTranscriber()
