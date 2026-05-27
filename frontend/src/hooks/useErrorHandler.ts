import { useState, useCallback } from "react";

export interface APIError {
  status: string;
  message: string;
  error_code: string;
  details?: string;
  context?: Record<string, unknown>;
}

export interface ErrorState {
  error: APIError | null;
  isError: boolean;
}

/**
 * Hook para manejar errores de API de manera consistente.
 * Extrae el error estructurado de la respuesta y proporciona métodos para manejarlo.
 */
export function useErrorHandler() {
  const [error, setError] = useState<APIError | null>(null);

  const extractError = useCallback((err: unknown): APIError | null => {
    // Si es un error estructurado de nuestra API
    if (err instanceof Error) {
      const errorData = (err as any).response?.data;
      if (errorData && typeof errorData === "object") {
        if ("error_code" in errorData && "message" in errorData) {
          return {
            status: errorData.status || "error",
            message: errorData.message,
            error_code: errorData.error_code,
            details: errorData.details,
            context: errorData.context,
          };
        }
      }

      // Si es un error desconocido, crear uno estructurado
      return {
        status: "error",
        message: err.message || "Error desconocido",
        error_code: "UNKNOWN_ERROR",
      };
    }

    // Si es un objeto con propiedades de error
    if (typeof err === "object" && err !== null) {
      if ("message" in err && "error_code" in err) {
        return err as APIError;
      }
    }

    // Fallback para errores genéricos
    return {
      status: "error",
      message: "Ocurrió un error inesperado",
      error_code: "UNKNOWN_ERROR",
    };
  }, []);

  const handleError = useCallback(
    (err: unknown) => {
      const apiError = extractError(err);
      setError(apiError);
      console.error("API Error:", apiError);
      return apiError;
    },
    [extractError]
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    error,
    isError: error !== null,
    handleError,
    clearError,
    extractError,
  };
}
