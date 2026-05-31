"""
Generador de keywords visuales para búsqueda de imágenes via LLM.

Sustituye el algoritmo nemotécnico fijo por una consulta al modelo de IA
configurado en AI_PROVIDER, manteniendo el mismo contrato que el resto de
adaptadores de IA del proyecto.
"""

from typing import Optional
from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot.image_query_generator")

_PROMPT = """\
Eres un experto en búsqueda de imágenes de noticias. Tu tarea es extraer \
los conceptos visuales más representativos de un artículo para buscar imágenes \
relevantes en Unsplash y Google Images.

REGLAS:
- Devuelve entre 3 y 5 conceptos visuales separados por comas
- Prioriza: personas concretas, lugares, eventos, objetos físicos visibles
- Usa sustantivos específicos, no adjetivos ni verbos
- Si hay un personaje público, inclúyelo (ej: "Netanyahu", "Trump")
- Si hay un lugar reconocible, inclúyelo (ej: "Gaza", "Kremlin", "Wall Street")
- NO uses palabras genéricas: "noticia", "información", "situación", "hecho"
- NO uses stopwords ni artículos
- Los conceptos deben ser buscables visualmente en un banco de imágenes
- Responde SOLO con los conceptos separados por comas, sin explicaciones

EJEMPLOS:
Artículo sobre bombardeos en Gaza → "Gaza, bombardeo, edificio destruido, civiles, explosión"
Artículo sobre crisis económica en Argentina → "Buenos Aires, bolsa, inflación, peso, manifestación"
Artículo sobre erupción volcánica → "volcán, lava, erupción, ceniza, evacuación"

ARTÍCULO:
Título: {titulo}
Contenido: {contenido}

CONCEPTOS VISUALES:"""


def generar_keywords_visuales_con_llm(
    title: str,
    content: str = "",
) -> Optional[list[str]]:
    """
    Genera keywords visuales para búsqueda de imágenes usando el modelo IA configurado.

    Usa AI_PROVIDER de Settings, igual que el resto de adaptadores de IA.
    Devuelve None si falla, para que el llamador pueda usar el algoritmo de fallback.

    Args:
        title: título del artículo o post
        content: contenido del artículo (se trunca a 1500 chars)

    Returns:
        Lista de 3-5 conceptos visuales, o None si falla
    """
    if not title:
        return None

    contenido_truncado = content[:1500] if content else ""

    prompt = _PROMPT.format(titulo=title, contenido=contenido_truncado)

    try:
        from src.shared.adapters.ai.ai_factory import get_ai_adapter

        model = get_ai_adapter(Settings.AI_PROVIDER)

        result = model.generate(
            prompt=prompt,
            temperature=0.1,
            max_tokens=80,
        )

        raw = result.strip().split("\n")[0].strip()
        raw = raw.strip('"').strip("'").strip()

        if not raw:
            logger.warning("[IMAGE_QUERY] LLM devolvió respuesta vacía")
            return None

        keywords = [k.strip() for k in raw.split(",") if k.strip()]
        keywords = [k for k in keywords if len(k) > 2][:5]

        if not keywords:
            logger.warning("[IMAGE_QUERY] No se extrajeron keywords válidas")
            return None

        logger.info(f"[IMAGE_QUERY] Keywords generadas: {keywords} para '{title[:40]}'")
        return keywords

    except Exception as e:
        logger.error(f"[IMAGE_QUERY] Error generando keywords con LLM: {e}")
        return None
