"""Helpers de test para la inyección de proveedores de imágenes (B20.4f).

`BasePipelineUseCase` ya no importa los adaptadores de imágenes: recibe un
`ImageProviders` (VO) con las factories inyectadas. Los tests construyen ese
VO con dobles de prueba.

Uso típico:

    from image_helpers import build_image_providers

    pipeline = AudioPipelineUseCase(
        ...,
        image_providers=build_image_providers(),
    )
"""

from unittest.mock import Mock

from src.shared.domain.services.image_providers import ImageProviders


class _FakeImageFetcher:
    """Fetcher de imágenes de mentira: devuelve los posts sin tocar."""

    def __init__(self, mode: str = "news"):
        self.mode = mode

    def fetch_for_posts(self, posts):
        return posts


class _FakeImageEnricher:
    """Enriquecedor de imágenes de mentira: devuelve los posts sin tocar."""

    def __init__(self, mode: str = "news"):
        self.mode = mode

    def enrich(self, posts):
        return posts


def build_image_providers():
    """Construye un `ImageProviders` con dobles de prueba.

    Returns:
        ImageProviders con factories que devuelven dobles sin efectos.
    """
    return ImageProviders(
        enricher_factory=Mock(side_effect=lambda mode: _FakeImageEnricher(mode)),
        wikimedia_factory=Mock(side_effect=lambda mode: _FakeImageFetcher(mode)),
        google_factory=Mock(side_effect=lambda mode: _FakeImageFetcher(mode)),
        unsplash_factory=Mock(side_effect=lambda mode: _FakeImageFetcher(mode)),
    )
