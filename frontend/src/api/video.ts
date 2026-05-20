import { api, PipelineResponse } from "./client";

export interface VideoProcessRequest {
  url: string;
  provider?: string;
  tema?: string;
}

export interface VideoPipelineRequest {
  url: string;
  tema: string;
  no_publish?: boolean;
}

export const processVideo = (req: VideoProcessRequest): Promise<PipelineResponse> =>
  api.post<PipelineResponse>("/video/process", req).then((r) => r.data);

export const runVideoPipeline = (req: VideoPipelineRequest): Promise<PipelineResponse> =>
  api.post<PipelineResponse>("/video/pipeline", req).then((r) => r.data);
