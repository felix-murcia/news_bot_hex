"""Error handling and structured error responses for API endpoints."""

from typing import Optional, Dict, Any
from fastapi import HTTPException
from pydantic import BaseModel
from config.logging_config import get_logger

logger = get_logger("news_bot.api.error_handler")


class ErrorResponse(BaseModel):
    """Structured error response."""
    status: str = "error"
    message: str  # User-friendly message
    error_code: str  # Machine-readable error code
    details: Optional[str] = None  # Additional details for frontend
    context: Optional[Dict[str, Any]] = None  # Additional context (logged but not shown to user)


def log_exception(error_code: str, exception: Exception, context: Optional[Dict[str, Any]] = None):
    """Log exception with full traceback while preparing user-friendly message."""
    logger.error(
        f"[{error_code}] {type(exception).__name__}: {str(exception)}",
        exc_info=True,
        extra={"context": context}
    )


def http_error(
    status_code: int,
    error_code: str,
    message: str,
    exception: Optional[Exception] = None,
    details: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    """Create a properly formatted HTTPException with error response.

    Args:
        status_code: HTTP status code (400, 500, etc)
        error_code: Machine-readable error code (e.g., "CONTENT_EXTRACTION_FAILED")
        message: User-friendly error message
        exception: Original exception for logging
        details: Additional details to include in response
        context: Context data for logging (not shown to user)

    Returns:
        HTTPException with structured error response
    """
    if exception:
        log_exception(error_code, exception, context)
    else:
        logger.warning(f"[{error_code}] {message}")

    error_response = ErrorResponse(
        status="error",
        message=message,
        error_code=error_code,
        details=details,
    )

    return HTTPException(
        status_code=status_code,
        detail=error_response.model_dump(exclude_none=True)
    )


# Common error codes and messages
ERROR_CODES = {
    "INVALID_URL": ("URL no válida o vacía", "Verifica que la URL sea correcta y accesible"),
    "CONTENT_EXTRACTION_FAILED": ("No se pudo extraer el contenido", "El sitio web puede estar bloqueado o no accesible"),
    "CONTENT_TOO_SHORT": ("Contenido insuficiente", "El artículo debe tener al menos 100 caracteres"),
    "ARTICLE_GENERATION_FAILED": ("Error generando artículo", "El servicio de IA no respondió. Intenta de nuevo."),
    "TWEET_GENERATION_FAILED": ("Error generando tweet", "No se pudo generar el resumen para redes sociales"),
    "TTS_GENERATION_FAILED": ("Error generando audio", "El servicio de TTS no está disponible"),
    "VIDEO_GENERATION_FAILED": ("Error generando vídeo", "No se pudo crear el vídeo con el audio"),
    "DATABASE_ERROR": ("Error de base de datos", "El servicio de base de datos no está disponible"),
    "SERVICE_UNAVAILABLE": ("Servicio no disponible", "Intenta de nuevo en unos momentos"),
    "INVALID_REQUEST": ("Solicitud inválida", "Verifica los parámetros enviados"),
    "PIPELINE_ERROR": ("Error en el pipeline", "Algo salió mal durante el procesamiento"),
}


def get_error_message(error_code: str, default_msg: str = "Error desconocido") -> tuple:
    """Get user-friendly message and details for error code."""
    if error_code in ERROR_CODES:
        message, details = ERROR_CODES[error_code]
        return message, details
    return default_msg, None
