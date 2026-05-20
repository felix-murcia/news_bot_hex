import { PipelineResponse } from "./client";

interface MutationLike {
  isPending: boolean;
  data?: PipelineResponse;
  error: unknown;
}

export function mutationState(m: MutationLike) {
  return {
    loading: m.isPending,
    response: (m.data ?? null) as PipelineResponse | null,
    error: m.error ? String((m.error as Error).message) : null,
  };
}
