"""
Generador de keywords visuales en inglés para búsqueda de imágenes via LLM.

Genera las keywords en inglés para que la comparación de relevancia
funcione correctamente contra las descripciones de Unsplash (también en inglés).
"""

from typing import Optional
from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot.image_query_generator")

_PROMPT = """\
You are an expert in image search for news articles. Extract the most representative \
visual concepts from the article to search for relevant images on Unsplash.

RULES:
- Return between 3 and 5 visual concepts separated by commas
- Prioritize: specific people, places, events, visible physical objects
- Use specific nouns, not adjectives or verbs
- If there is a public figure, include them (e.g., "Netanyahu", "Trump")
- If there is a recognizable place, include it (e.g., "Gaza", "Kremlin", "Wall Street")
- DO NOT use generic words: "news", "information", "situation", "fact"
- DO NOT use stopwords or articles
- Concepts must be visually searchable on a stock image site
- Reply ONLY with the concepts separated by commas, no explanations
- ALWAYS reply in English

EXAMPLES:
Article about bombings in Gaza → "Gaza, bombing, destroyed building, civilians, explosion"
Article about economic crisis in Argentina → "Buenos Aires, stock market, inflation, peso, protest"
Article about volcanic eruption → "volcano, lava, eruption, ash, evacuation"

ARTICLE:
Title: {titulo}
Content: {contenido}

VISUAL CONCEPTS:"""


def generar_keywords_visuales_con_llm(
    title: str,
    content: str = "",
) -> Optional[list[str]]:
    """
    Genera keywords visuales en inglés para búsqueda de imágenes.

    Devuelve keywords en inglés para que el filtro de relevancia funcione
    correctamente contra las descripciones de Unsplash (también en inglés).
    Devuelve None si falla.
    """
    if not title:
        return None

    contenido_truncado = content[:1500] if content else ""
    prompt = _PROMPT.format(titulo=title, contenido=contenido_truncado)

    try:
        from src.shared.adapters.ai.ai_factory import get_ai_adapter

        model = get_ai_adapter(Settings.AI_PROVIDER)
        result = model.generate(prompt=prompt, temperature=0.1, max_tokens=80)

        raw = result.strip().split("\n")[0].strip()
        raw = raw.strip('"').strip("'").strip()

        if not raw:
            logger.warning("[IMAGE_QUERY] LLM returned empty response")
            return None

        keywords = [k.strip() for k in raw.split(",") if k.strip()]
        keywords = [k for k in keywords if len(k) > 2][:5]

        if not keywords:
            logger.warning("[IMAGE_QUERY] No valid keywords extracted")
            return None

        logger.info(f"[IMAGE_QUERY] Keywords (en): {keywords} for '{title[:40]}'")
        return keywords

    except Exception as e:
        logger.error(f"[IMAGE_QUERY] Error generating keywords: {e}")
        return None
