"""
Web Search Query Generator via LLM.

En vez de usar heurística con palabras sueltas, se consulta al modelo de IA
para que compose una query de búsqueda coherente y precisa a partir de
la transcripción. Esto produce queries mucho más relevantes para la búsqueda web.
"""

from typing import Optional
from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("web_search.llm_query")


# Prompt mínimo y directo para generación de query de búsqueda
_QUERY_PROMPT = """\
Eres un experto en búsqueda de información. Tu única tarea es generar una query de búsqueda para encontrar noticias relacionadas con el contenido proporcionado.

REGLAS:
- Genera UNA SOLA query de 3-5 palabras máximo
- La query debe ser coherente y tener sentido como frase de búsqueda
- Prioriza nombres propios, lugares, eventos y temas principales
- NO incluyas palabras genéricas como "noticias", "video", "última hora", "gracias"
- NO añadas explicaciones, solo la query
- La query debe ser en el idioma del contenido (español o inglés)
- Separa las palabras con espacios normales

EJEMPLOS CORRECTOS:
- "Papa León XIV Trump alto el fuego Irán"
- "refinería Komsomolsk Rusia trabajadores huelga"
- "Israel Iran strikes Trump deadline"

EJEMPLOS INCORRECTOS:
- "Gracias canal seguridad últimas noticias"
- "video papa trump"
- "noticias Irán hoy"

CONTENIDO:
{contenido}

QUERY (solo la query, nada más):"""


def generar_query_con_llm(transcripcion: str, tema: str = "") -> Optional[str]:
    """
    Genera una query de búsqueda usando el modelo de IA configurado.

    Args:
        transcripcion: Texto de la transcripción del video/audio
        tema: Tema o categoría del contenido (opcional)

    Returns:
        Query de búsqueda como string, o None si falla
    """
    if not transcripcion or len(transcripcion) < 100:
        logger.debug("[WEB_SEARCH] Transcripción demasiado corta")
        return None

    # Limitar contenido para eficiencia (primeras 2000 chars)
    contenido = transcripcion[:2000]

    prompt = _QUERY_PROMPT.format(contenido=contenido)

    try:
        from src.shared.adapters.ai.ai_factory import get_ai_adapter

        model = get_ai_adapter(Settings.AI_PROVIDER)

        result = model.generate(
            prompt=prompt,
            temperature=0.1,  # Muy baja para respuestas deterministas
            max_tokens=60,    # Solo necesitamos una query corta
        )

        # Limpiar resultado: solo la primera línea, sin explicaciones
        query = result.strip().split("\n")[0].strip()

        # Quitar comillas si las tiene
        query = query.strip('"').strip("'").strip()

        # Limitar longitud
        if len(query) > 150:
            query = query[:150].rsplit(" ", 1)[0]

        if query:
            # Añadir tema si es relevante y no genérico
            if tema and tema not in ("General", "Noticias", "Videos"):
                query = f"{query} {tema}"
            logger.info(f"[WEB_SEARCH] Query generada por LLM: '{query}'")
            return query
        else:
            logger.warning("[WEB_SEARCH] LLM devolvió query vacía")
            return None

    except Exception as e:
        logger.error(f"[WEB_SEARCH] Error generando query con LLM: {e}")
        return None
