"""Centralized error handlers for FastAPI app (exception_handler decorators)."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from config.logging_config import get_logger
from src.news.domain.exceptions import RepositoryError

logger = get_logger("news_bot.api.error_handlers")


def register_error_handlers(app: FastAPI) -> None:
    """Register global error handlers with FastAPI app."""

    @app.exception_handler(RepositoryError)
    async def repository_error_handler(request: Request, exc: RepositoryError):
        """Handle repository errors with 503 Service Unavailable."""
        logger.error(f"[REPOSITORY_ERROR] {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error_code": "DATABASE_ERROR",
                "message": "Error de base de datos",
                "details": "El servicio de base de datos no está disponible",
            }
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle validation errors with 400 Bad Request."""
        logger.warning(f"[VALIDATION_ERROR] {str(exc)}")
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error_code": "INVALID_REQUEST",
                "message": "Solicitud inválida",
                "details": str(exc),
            }
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        """Handle unexpected errors with 500 Internal Server Error."""
        error_id = id(exc)
        logger.error(
            f"[INTERNAL_ERROR] {error_id}: {type(exc).__name__}: {str(exc)}",
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "Error interno del servidor",
                "details": f"Error ID: {error_id}. Contacta al administrador.",
            }
        )
