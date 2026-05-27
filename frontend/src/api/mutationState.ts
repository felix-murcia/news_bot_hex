import { PipelineResponse } from "./client";
import { APIError } from "../hooks/useErrorHandler";

interface MutationLike {
  isPending: boolean;
  data?: PipelineResponse;
  error: unknown;
}

export function mutationState(m: MutationLike) {
  let error: string | APIError | null = null;

  if (m.error) {
    const err = m.error as any;
    // Try to extract structured error from response
    if (err.response?.data) {
      const data = err.response.data;
      if (typeof data === "object" && "error_code" in data && "message" in data) {
        error = data as APIError;
      }
    }
    // Fallback to error message
    if (!error) {
      error = err.message || String(err);
    }
  }

  return {
    loading: m.isPending,
    response: (m.data ?? null) as PipelineResponse | null,
    error,
  };
}
