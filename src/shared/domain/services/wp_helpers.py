"""Value object con las funciones del adaptador de WordPress (B20.4e).

`application/` no puede importar `src.shared.adapters.wordpress_publisher` ni
`src.shared.adapters.wordpress_token_manager`: son adaptadores concretos
(hablan HTTP con WordPress y gestionan el token JWT).

El caso de uso base de los pipelines (`BasePipelineUseCase`) necesita:
  - validar el token antes de publicar (fail-fast), y
  - publicar el post con categoría, tags, imagen destacada y audio.

Ambas capacidades entran como un único VO de callables, igual que
`SeoHelpers` (B20.4c) y `AiProviders` (B20.4d): un solo parámetro que
propagar por la jerarquía de pipelines.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class WpHelpers:
    """Funciones de publicación en WordPress.

    Attributes:
        get_valid_wp_token: `f() -> str`. Devuelve un token JWT válido o
            lanza `RuntimeError`. Se invoca antes de cada publicación.
        publish_post: `f(**kwargs) -> Optional[str]`. Crea el post y
            devuelve su URL (o `None` si no se pudo publicar).
        ensure_category: `f(name) -> Optional[int]`. Devuelve el id de la
            categoría, creándola si no existe.
        ensure_tag: `f(name) -> Optional[int]`. Devuelve el id del tag,
            creándolo si no existe.
        upload_image_from_url: `f(url, **kwargs) -> Optional[int]`. Sube una
            imagen remota como media y devuelve su id.
        upload_audio: `f(path) -> Optional[int]`. Sube un audio MP3 y
            devuelve su id de media.
        rest_url: `f(endpoint) -> str`. Construye la URL de la API REST.
        get_headers: `f() -> dict`. Cabeceras de autenticación (token
            auto-refrescado).
    """

    get_valid_wp_token: Callable[[], str]
    publish_post: Callable[..., Optional[str]]
    ensure_category: Callable[..., Optional[int]]
    ensure_tag: Callable[..., Optional[int]]
    upload_image_from_url: Callable[..., Optional[int]]
    upload_audio: Callable[..., Optional[int]]
    rest_url: Callable[[str], str]
    get_headers: Callable[[], Dict[str, Any]]
