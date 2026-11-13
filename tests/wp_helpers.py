"""Helpers de test para la inyección de WordPress (B20.4e).

`BasePipelineUseCase` ya no importa los adaptadores de WordPress: recibe un
`WpHelpers` (VO) con los callables inyectados. Los tests construyen ese VO
con dobles de prueba.

Uso típico:

    from wp_helpers import build_wp_helpers

    pipeline = AudioPipelineUseCase(
        ...,
        wp_helpers=build_wp_helpers(),
    )
"""

from unittest.mock import Mock

from src.shared.domain.services.wp_helpers import WpHelpers


def build_wp_helpers(
    *,
    token: str = "test-token",
    published_url: str = "https://test.example/?p=1",
    category_id: int = 1,
    tag_id: int = 2,
    media_id: int = 3,
):
    """Construye un `WpHelpers` con dobles de prueba.

    Args:
        token: Token que devuelve `get_valid_wp_token`.
        published_url: URL que devuelve `publish_post`.
        category_id: Id que devuelven `ensure_category` y `ensure_tag`.
        tag_id: Id que devuelve `ensure_tag`.
        media_id: Id que devuelven `upload_image_from_url` y `upload_audio`.

    Returns:
        WpHelpers con callables simulados.
    """
    return WpHelpers(
        get_valid_wp_token=Mock(return_value=token),
        publish_post=Mock(return_value=published_url),
        ensure_category=Mock(return_value=category_id),
        ensure_tag=Mock(return_value=tag_id),
        upload_image_from_url=Mock(return_value=media_id),
        upload_audio=Mock(return_value=media_id),
        rest_url=Mock(return_value="https://test.example/wp-json/wp/v2/media/3"),
        get_headers=Mock(return_value={"Authorization": "Bearer test-token"}),
    )
