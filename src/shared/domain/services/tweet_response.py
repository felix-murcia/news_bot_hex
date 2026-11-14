"""Validación de la respuesta del TweetGeopoliticsAgent.

El agente se instruye a responder con JSON estricto:

    {"tweet": "..."}

El modelo NO decide publicabilidad; solo redacta. La validación de calidad
(tweet bien formado, sin JSON, sin URLs truncadas) la hace el sistema
(truncate_social_post + _validate_social_text), no el modelo.
"""

import json
import re
from dataclasses import dataclass

# Respuesta a página de error devuelta por el proveedor de contenido (no es
# negación del modelo, es un fallo del fetch/traducción upstream).
ERROR_PAGE_PATTERNS = [
    "error 500",
    "server error",
    "that's an error",
    "403 forbidden",
]


@dataclass
class TweetResponse:
    """Resultado de generar un tweet.

    publishable: True si se extrajo un tweet válido del JSON.
    text: el tweet extraído.
    reason: motivo técnico si falló (JSON inválido, tweet vacío, etc.).
    """

    publishable: bool
    text: str = ""
    reason: str = ""


def extraer_json(raw: str):
    """Extrae el primer objeto JSON de una respuesta del modelo.

    Tolerante a cercas ```json y a texto alrededor del objeto. Devuelve el
    dict, o None si no hay un objeto JSON válido.
    """
    if not raw:
        return None
    texto = raw.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```[a-zA-Z]*\s*", "", texto)
        texto = re.sub(r"\s*```$", "", texto)
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio == -1 or fin <= inicio:
        return None
    try:
        data = json.loads(texto[inicio:fin + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _contiene_pagina_de_error(texto: str, title: str = "") -> bool:
    texto_bajo = texto.lower()
    return any(
        p in texto_bajo or (title and p in title.lower())
        for p in ERROR_PAGE_PATTERNS
    )


def validar_tweet(raw: str, title: str = "") -> TweetResponse:
    """Comprueba la respuesta cruda del agente de tweets.

    Espera JSON: {"tweet": "..."}. Extrae el tweet y valida que no esté
    vacío y no sea una página de error. Si el JSON falla, intenta tratar
    la respuesta como texto plano.
    """
    data = extraer_json(raw)
    if data is not None and "tweet" in data:
        tweet = str(data.get("tweet") or "").strip()
        if not tweet:
            return TweetResponse(
                publishable=False,
                reason="El modelo devolvió JSON con tweet vacío",
            )
        if _contiene_pagina_de_error(tweet, title):
            return TweetResponse(
                publishable=False,
                reason="El tweet extraído parece una página de error",
            )
        return TweetResponse(publishable=True, text=tweet)

    # Fallback: respuesta sin JSON válido -> tratar como texto plano
    texto = (raw or "").strip()
    if not texto:
        return TweetResponse(publishable=False, reason="Respuesta vacía del modelo")
    if _contiene_pagina_de_error(texto, title):
        return TweetResponse(
            publishable=False, reason="Posible página de error devuelta por el proveedor"
        )
    # Si llega aquí, el modelo devolvió texto plano sin JSON -> usarlo
    return TweetResponse(publishable=True, text=texto)
