"""
Prompt Loader Utility.

Carga prompts desde archivos Markdown para los agentes de IA.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_PROMPT_CACHE: Dict[str, str] = {}


def load_prompt(agent_name: str) -> str:
    """
    Carga un prompt desde archivo Markdown.

    Args:
        agent_name: Nombre del agente (ej: "refinamiento", "tecnico", etc.)

    Returns:
        Contenido del prompt como string.
    """
    if agent_name in _PROMPT_CACHE:
        return _PROMPT_CACHE[agent_name]

    prompt_file = _PROMPTS_DIR / f"{agent_name}.md"

    if not prompt_file.exists():
        logger.warning(f"[PROMPT_LOADER] Prompt '{agent_name}.md' no encontrado")
        return _get_default_prompt(agent_name)

    try:
        content = prompt_file.read_text(encoding="utf-8")
        _PROMPT_CACHE[agent_name] = content
        logger.info(f"[PROMPT_LOADER] Prompt '{agent_name}' cargado")
        return content
    except Exception as e:
        logger.error(f"[PROMPT_LOADER] Error cargando prompt '{agent_name}': {e}")
        return _get_default_prompt(agent_name)


def _get_default_prompt(agent_name: str) -> str:
    """Prompt por defecto si no se encuentra el archivo."""
    defaults = {
        "refinamiento": "Eres un editor experto. Refina y mejora el siguiente texto.",
        "tecnico": "Convierte el siguiente texto a formato técnico profesional.",
        "ejecutivo": "Resume el siguiente texto en formato ejecutivo conciso.",
        "project_manager": "Estructura el siguiente texto para gestión de proyectos.",
        "product_manager": "Estructura el siguiente texto para gestión de productos.",
        "quality_assurance": "Revisa el siguiente texto y señala problemas de calidad.",
        "bullet": "Convierte el siguiente texto a formato de viñetas.",
        "comparative": "Realiza un análisis comparativo del siguiente texto.",
    }
    return defaults.get(
        agent_name, f"Eres un asistente de IA. Procesa el siguiente texto."
    )


def clear_cache():
    """Limpia el cache de prompts."""
    global _PROMPT_CACHE
    _PROMPT_CACHE = {}
    logger.info("[PROMPT_LOADER] Cache limpiado")


def reload_prompt(agent_name: str) -> str:
    """Recarga un prompt específico (limpia cache primero)."""
    _PROMPT_CACHE.pop(agent_name, None)
    return load_prompt(agent_name)
