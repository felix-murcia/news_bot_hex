"""AI module - Interfaz unificada para modelos de IA."""

from src.ai.base.model_interface import AIModel
from src.ai.factory import get_ai_model, list_providers

__all__ = ["AIModel", "get_ai_model", "list_providers"]
