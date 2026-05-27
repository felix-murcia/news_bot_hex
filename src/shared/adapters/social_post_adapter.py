import re
from typing import Optional

from config.settings import Settings

DEFAULT_SOCIAL_NETWORKS = ("x", "twitter", "bluesky", "mastodon")


def get_social_post_limit(limit: Optional[int] = None) -> int:
    """Devuelve el límite de caracteres para publicaciones sociales.

    Si no se pasa un límite explícito, usa el más restrictivo de las
    plataformas X/Twitter, Bluesky y Mastodon para asegurar compatibilidad.
    """
    if limit is not None:
        return limit

    values = [
        Settings.POST_LIMITS.get(network)
        for network in DEFAULT_SOCIAL_NETWORKS
        if Settings.POST_LIMITS.get(network) is not None
    ]
    return min(values) if values else 280


def truncate_social_post(text: str, limit: Optional[int] = None) -> str:
    """Trunca un texto social respetando hashtags y el límite más estricto.

    Reglas de negocio:
    - Si el texto excede el límite, se eliminan hashtags de derecha a izquierda.
    - Se mantiene exactamente 1 hashtag si es necesario.
    - Si aún excede, se trunca el texto en el último espacio completo (SIN añadir "...").
    - NUNCA se añaden puntos suspensivos para mantener profesionalismo.
    """
    tweet = (text or "").strip()
    limit = get_social_post_limit(limit)
    if len(tweet) <= limit:
        return tweet

    # Extraer hashtags y texto plano
    hashtags = re.findall(r"#\w+", tweet)
    plain_text = re.sub(r"#\w+", "", tweet)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()

    # Estrategia 1: Eliminar hashtags uno a uno hasta que quepa
    if hashtags:
        trimmed_hashtags = hashtags.copy()

        while len(trimmed_hashtags) > 1:
            candidate = f"{plain_text} {' '.join(trimmed_hashtags)}".strip()
            if len(candidate) <= limit:
                return candidate
            trimmed_hashtags.pop()

        # Probar con solo 1 hashtag
        first_hashtag = trimmed_hashtags[0]
        candidate = f"{plain_text} {first_hashtag}".strip()
        if len(candidate) <= limit:
            return candidate

        # Estrategia 2: Truncar texto en última palabra completa + 1 hashtag
        available_space = limit - len(first_hashtag) - 1
        if available_space > 10:
            # Truncar en el último espacio completo (sin "...")
            content_part = plain_text[:available_space].rsplit(" ", 1)[0]
            if not content_part:
                content_part = plain_text[:available_space]
            return f"{content_part} {first_hashtag}".strip()

        # Caso extremo: solo hashtag
        return first_hashtag[:limit]

    # Sin hashtags: truncar en última palabra completa y añadir "..."
    if limit > 3:
        available = limit - 3  # espacio para texto antes de "..."
        truncated = tweet[:available].rsplit(" ", 1)[0]
        if not truncated:
            truncated = tweet[:available]
        return truncated.rstrip() + "..."
    # Límite muy pequeño, solo truncar sin "..."
    return tweet[:limit]
