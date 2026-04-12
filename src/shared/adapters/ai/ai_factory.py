"""
AI Adapter Factory (Hexagonal Architecture).

Factory para obtener instancias de adapters de IA.
"""

import logging
from typing import Dict, Optional
from src.shared.domain.ports.ai_model_port import AIModelPort
from config.settings import Settings


logger = logging.getLogger(__name__)


def get_ai_adapter(
    provider: str = Settings.AI_PROVIDER,
    config: Optional[Dict] = None,
    validate_key: bool = False,
) -> AIModelPort:
    """
    Get an instance of the specified AI adapter.

    Args:
        provider: Provider name ("gemini", "openrouter", "local", "mock", "groq").
        config: Optional configuration for the adapter.
        validate_key: If True, validate API key on initialization.

    Returns:
        AIModelPort instance.

    Raises:
        ValueError: If provider is invalid or API key validation fails.
    """
    config = config or {}
    provider = provider.lower()

    if provider not in Settings.AI_ADAPTER_MAP:
        available = ", ".join(Settings.AI_ADAPTER_MAP.keys())
        raise ValueError(f"Proveedor '{provider}' no válido. Disponibles: {available}")

    import importlib

    module_path = Settings.AI_ADAPTER_MAP[provider]
    module_name, class_name = module_path.rsplit(".", 1)

    try:
        module = importlib.import_module(module_name)
        adapter_class = getattr(module, class_name)
        instance = adapter_class(config, validate_on_init=validate_key)

        logger.info(f"[AI_FACTORY] Adapter '{provider}' instantiated")
        return instance

    except ImportError as e:
        logger.error(f"[AI_FACTORY] Error importando {provider}: {e}")
        raise ValueError(f"No se pudo cargar el adapter '{provider}': {e}")


def list_providers() -> list:
    """Lista todos los proveedores disponibles."""
    return list(Settings.AI_ADAPTER_MAP.keys())


# Alias para compatibilidad
get_ai_model = get_ai_adapter
