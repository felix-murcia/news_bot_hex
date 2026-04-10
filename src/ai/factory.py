"""
Factory para obtener instancias de modelos de IA.

Proporciona una forma unificada de obtener cualquier modelo
sin acoplar el código a implementaciones específicas.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_PROVIDER_MAP = {
    "gemini": "src.ai.implementations.gemini.gemini_model.GeminiAIModel",
    "openrouter": "src.ai.implementations.openrouter.openrouter_model.OpenRouterAIModel",
    "local": "src.ai.implementations.local.local_model.LocalAIModel",
    "mock": "src.ai.implementations.local.local_model.MockAIModel",
}


def get_ai_model(
    provider: str = "gemini",
    config: Optional[Dict] = None,
) -> "AIModel":
    """
    Obtiene una instancia del modelo de IA especificado.

    Args:
        provider: Nombre del proveedor ("gemini", "openrouter", "local", "mock").
        config: Configuración opcional para el modelo.

    Returns:
        Instancia de AIModel.

    Raises:
        ValueError: Si el proveedor no es válido.
    """
    config = config or {}
    provider = provider.lower()

    if provider not in _PROVIDER_MAP:
        available = ", ".join(_PROVIDER_MAP.keys())
        raise ValueError(f"Proveedor '{provider}' no válido. Disponibles: {available}")

    import importlib

    module_path = _PROVIDER_MAP[provider]
    module_name, class_name = module_path.rsplit(".", 1)

    try:
        module = importlib.import_module(module_name)
        model_class = getattr(module, class_name)
        instance = model_class(config)

        logger.info(f"[AI_FACTORY] Modelo '{provider}' instanciado")
        return instance

    except ImportError as e:
        logger.error(f"[AI_FACTORY] Error importando {provider}: {e}")
        raise ValueError(f"No se pudo cargar el modelo '{provider}': {e}")


def list_providers() -> list:
    """Lista todos los proveedores disponibles."""
    return list(_PROVIDER_MAP.keys())


from src.ai.base.model_interface import AIModel
