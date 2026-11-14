"""Value object con las fábricas de proveedores de imágenes (B20.4f).

`application/` no puede importar `src.shared.adapters.image_enricher`,
`wikimedia_fetcher`, `google_images_fetcher` ni `unsplash_fetcher`: son
adaptadores concretos (hablan HTTP con APIs externas).

El pipeline base (`BasePipelineUseCase`) los instancia en runtime, cada uno
con el `mode` del pipeline (audio/video/news). Se inyectan como factories
que reciben ese `mode` y devuelven el adaptador listo.

Un solo VO, un solo parámetro que propagar por la jerarquía de pipelines
(mismo patrón que `SeoHelpers`, `AiProviders` y `WpHelpers`).
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ImageProviders:
    """Factories de los proveedores de imágenes del pipeline.

    Todos los factories reciben el `mode` del pipeline (`"news"`, `"audio"`,
    `"video"`) y devuelven un adaptador con:
      - `enrich(posts) -> list` (enriquecedor), y
      - `fetch_for_posts(posts) -> list` (fetchers).

    Attributes:
        enricher_factory: `f(mode) -> enricher`.
        wikimedia_factory: `f(mode) -> fetcher` (Wikimedia Commons; ignora
            el `mode`).
        google_factory: `f(mode) -> fetcher` (Google Images).
        unsplash_factory: `f(mode) -> fetcher` (Unsplash, último recurso).
    """

    enricher_factory: Callable[[str], Any]
    wikimedia_factory: Callable[[str], Any]
    google_factory: Callable[[str], Any]
    unsplash_factory: Callable[[str], Any]
