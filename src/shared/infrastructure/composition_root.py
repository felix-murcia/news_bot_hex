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
from src.news.domain.ports.metrics_repository_port import MetricsRepositoryPort
from src.shared.domain.services.ai_providers import AiProviders
from src.shared.domain.services.image_providers import ImageProviders
from src.shared.domain.services.wp_helpers import WpHelpers
from typing import Optional


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


def create_ai_providers() -> AiProviders:
    """Fábricas de adaptadores de IA y de agentes (B20.4d).

    Único punto donde `application/` obtiene los adaptadores concretos de IA.
    Los agentes se exponen como factories: cada uso crea una instancia nueva
    (relee el prompt del disco), igual que antes de la inyección.
    """
    from src.shared.adapters.ai.ai_factory import get_ai_adapter
    from src.shared.adapters.ai.agents import (
        ArticleAgent,
        ArticleFromContentAgent,
        TweetAgent,
        TweetGeopoliticsAgent,
    )

    return AiProviders(
        adapter_factory=get_ai_adapter,
        article_agent_factory=lambda ai_client: ArticleAgent(ai_client),
        article_from_content_agent_factory=lambda ai_client, source_type: (
            ArticleFromContentAgent(ai_client, source_type=source_type)
        ),
        tweet_agent_factory=lambda ai_client: TweetAgent(ai_client),
        tweet_geopolitics_agent_factory=lambda ai_client: TweetGeopoliticsAgent(
            ai_client
        ),
    )


def create_image_providers() -> ImageProviders:
    """Factories de proveedores de imágenes (B20.4f).

    Único punto donde `application/` obtiene los adaptadores de imágenes.
    Cada factory recibe el `mode` del pipeline y devuelve el adaptador
    listo, igual que se instanciaban inline antes de la inyección.
    """
    from src.shared.adapters.google_images_fetcher import GoogleImagesFetcher
    from src.shared.adapters.image_enricher import ImageEnricher
    from src.shared.adapters.unsplash_fetcher import UnsplashFetcher
    from src.shared.adapters.wikimedia_fetcher import WikimediaFetcher

    return ImageProviders(
        enricher_factory=lambda mode: ImageEnricher(mode=mode),
        wikimedia_factory=lambda mode: WikimediaFetcher(),
        google_factory=lambda mode: GoogleImagesFetcher(mode=mode),
        unsplash_factory=lambda mode: UnsplashFetcher(mode=mode),
    )


def create_wp_helpers() -> WpHelpers:
    """Funciones de publicación en WordPress (B20.4e).

    Único punto donde `application/` obtiene el adaptador de WordPress. Las
    funciones se inyectan como callables; el caso de uso no importa nada de
    `src.shared.adapters.wordpress_publisher` ni de `wordpress_token_manager`.
    """
    from src.shared.adapters.wordpress_publisher import (
        ensure_category,
        ensure_tag,
        get_headers,
        publish_post,
        rest_url,
        upload_audio,
        upload_image_from_url,
    )
    from src.shared.adapters.wordpress_token_manager import get_valid_wp_token

    return WpHelpers(
        get_valid_wp_token=get_valid_wp_token,
        publish_post=publish_post,
        ensure_category=ensure_category,
        ensure_tag=ensure_tag,
        upload_image_from_url=upload_image_from_url,
        upload_audio=upload_audio,
        rest_url=rest_url,
        get_headers=get_headers,
    )


def create_audio_converter_url_getter():
    """Callable que devuelve la URL del servicio de conversión de audio (B20.4e).

    `application/` no importa `audio_converter_factory`: recibe el callable
    inyectado y lo invoca donde lo necesita.
    """
    from src.shared.adapters.audio_converter_factory import get_audio_converter_url

    return get_audio_converter_url


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


def create_metrics_repository() -> MetricsRepositoryPort:
    from src.news.infrastructure.adapters.mongo_metrics_repository import MongoMetricsRepository
    from src.shared.adapters.mongo_db import get_database
    return MongoMetricsRepository(get_database())


def create_generated_articles_repository():
    from src.news.infrastructure.adapters.mongo_repositories import MongoGeneratedArticlesRepository
    from src.shared.adapters.mongo_db import get_database
    return MongoGeneratedArticlesRepository(get_database())


def create_generated_posts_repository():
    from src.news.infrastructure.adapters.mongo_repositories import MongoGeneratedPostsRepository
    from src.shared.adapters.mongo_db import get_database
    return MongoGeneratedPostsRepository(get_database())


def create_verified_news_repository():
    from src.news.infrastructure.adapters.mongo_repositories import MongoVerifiedNewsRepository
    from src.shared.adapters.mongo_db import get_database
    return MongoVerifiedNewsRepository(get_database())


# ============================================================
# Publishing — entry point functions (load from DB + publish)
# ============================================================

def run_wordpress():
    from src.shared.adapters.wordpress_publisher import run
    return run()


def run_bluesky():
    from src.shared.adapters.bluesky_publisher import run
    return run()


def run_facebook():
    from src.shared.adapters.facebook_publisher import run
    return run()


def run_mastodon():
    from src.shared.adapters.mastodon_publisher import run
    return run()


def run_image_unsplash(url: Optional[str] = None):
    from src.shared.adapters.unsplash_fetcher import run
    return run(url=url)


def run_image_google(url: Optional[str] = None):
    from src.shared.adapters.google_images_fetcher import run
    return run(url=url)


def create_social_publisher():
    from src.shared.adapters.publishers.social import SocialMediaPublisher
    return SocialMediaPublisher()


def create_debug_output_repository():
    from config.settings import Settings
    from src.shared.adapters.json_debug_output_repository import JsonDebugOutputRepository
    return JsonDebugOutputRepository(Settings.DATA_DIR)


def run_image_enricher(url: Optional[str] = None):
    from src.shared.adapters.image_enricher import run
    return run(url=url)
