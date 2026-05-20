import { api, PipelineResponse } from "./client";

export interface AudioProcessRequest {
  url: string;
  provider?: string;
  tema?: string;
}

export interface AudioPipelineRequest {
  url: string;
  tema: string;
  no_publish?: boolean;
}

export const processAudio = (req: AudioProcessRequest): Promise<PipelineResponse> =>
  api.post<PipelineResponse>("/audio/process", req).then((r) => r.data);

export const runAudioPipeline = (req: AudioPipelineRequest): Promise<PipelineResponse> =>
  api.post<PipelineResponse>("/audio/pipeline", req).then((r) => r.data);
