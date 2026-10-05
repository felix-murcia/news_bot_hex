"""Validación de la respuesta del TweetGeopoliticsAgent.

El agente se instruye a responder con JSON estricto:

    {"publicable": true, "tweet": "..."}
    {"publicable": false, "motivo": "..."}

Así la comprobación de publicabilidad es DETERMINISTA: la declara el propio
modelo, y no hay que adivinar frases. Los patrones de este módulo son segunda
capa (defensa en profundidad) para respuestas que no traen el JSON.
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

# Segunda capa: negaciones, apologías y respuestas meta del LLM en texto
# plano. Solo se consultan si la respuesta NO trajo el JSON estructurado.
REFUSAL_PATTERNS = [
    "no contiene información",
    "no contiene suficiente",
    "no es posible generar",
    "no es posible crear",
    "no es posible redactar",
    "no es posible elaborar",
    "no es posible escribir",
    "no puedo generar",
    "no puedo crear",
    "no puedo redactar",
    "no puedo elaborar",
    "no puedo escribir",
    "no hay información suficiente",
    "no hay material suficiente",
    "no es un hecho concreto",
    "el contenido proporcionado",
    "el contenido no contiene",
    "lo siento",
    # Respuesta meta: el LLM pide el contenido en vez de redactar la noticia
    # (vista en producción: BBC 2026-10-05, se publicó por error en Mastodon).
    "por favor, proporcione",
    "proporcione el contenido",
    "el contenido de la noticia",
    "el texto suministrado",
    "el texto proporcionado",
    "solo contiene enlaces",
    "etiquetas de navegación",
]


@dataclass
class TweetResponse:
    """Resultado de generar un tweet.

    publishable: True si hay un tweet publicable.
    text: el tweet (solo si publishable).
    reason: motivo de la negativa (solo si no publishable).
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


def _contiene_negacion(texto: str) -> bool:
    return any(p in texto.lower() for p in REFUSAL_PATTERNS)


def _contiene_pagina_de_error(texto: str, title: str = "") -> bool:
    texto_bajo = texto.lower()
    return any(
        p in texto_bajo or (title and p in title.lower())
        for p in ERROR_PAGE_PATTERNS
    )


def validar_tweet(raw: str, title: str = "") -> TweetResponse:
    """Comprueba la respuesta cruda del agente de tweets.

    Jerarquía:
    1. JSON estructurado (contrato del prompt): el campo `publicable` decide
       de forma determinista. El tweet del JSON pasa igualmente la segunda
       capa.
    2. Sin JSON: texto plano -> comprobación de página de error y de
       negaciones/respuestas meta (segunda capa).
    """
    data = extraer_json(raw)
    if data is not None and "publicable" in data:
        publicable = data.get("publicable")
        if isinstance(publicable, str):
            publicable = publicable.strip().lower() == "true"
        if not publicable:
            motivo = str(data.get("motivo") or "El modelo declinó el contenido")
            return TweetResponse(publishable=False, reason=motivo)
        tweet = str(data.get("tweet") or "").strip()
        if not tweet:
            return TweetResponse(
                publishable=False,
                reason="El modelo marcó publicable=true sin incluir el tweet",
            )
        if _contiene_pagina_de_error(tweet, title) or _contiene_negacion(tweet):
            return TweetResponse(
                publishable=False,
                reason="El tweet devuelto en el JSON no supera la comprobación de calidad",
            )
        return TweetResponse(publishable=True, text=tweet)

    texto = (raw or "").strip()
    if not texto:
        return TweetResponse(publishable=False, reason="Respuesta vacía del modelo")
    if _contiene_pagina_de_error(texto, title):
        return TweetResponse(
            publishable=False, reason="Posible página de error devuelta por el proveedor"
        )
    if _contiene_negacion(texto):
        return TweetResponse(
            publishable=False, reason="Negación o respuesta meta del modelo"
        )
    return TweetResponse(publishable=True, text=texto)
