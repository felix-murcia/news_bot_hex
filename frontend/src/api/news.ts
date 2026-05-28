import { api, PipelineResponse } from "./client";

export interface ProcessUrlRequest {
  url: string;
  provider?: string;
  use_ai?: boolean;
}

// Adjust these types if the backend response shape changes
export interface ProcessUrlData {
  title?: string;
  post?: string;
  mode?: string;
}

export interface RssArticle {
  title: string;
  url: string;
  source: string;
  publishedAt?: string;
}

export const fetchRss = (): Promise<PipelineResponse> =>
  api.post<PipelineResponse>("/news/rss").then((r) => r.data);

export const listRssArticles = (): Promise<RssArticle[]> =>
  api.get<RssArticle[]>("/news/rss").then((r) => r.data);

export const getSupportedProviders = (): Promise<{ providers: string[] }> =>
  api.get<PipelineResponse>("/admin/providers").then((r) => ({
    providers: (r.data.data?.providers as string[]) || [],
  }));

export const verifyNews = (): Promise<PipelineResponse> =>
  api.post<PipelineResponse>("/news/verify").then((r) => r.data);

export const softVerify = (): Promise<PipelineResponse> =>
  api.post<PipelineResponse>("/news/soft").then((r) => r.data);

export const generateArticle = (
  provider?: string,
  limit = 1
): Promise<PipelineResponse> =>
  api
    .post<PipelineResponse>("/news/article", null, {
      params: { provider, limit },
    })
    .then((r) => r.data);

export const generateContent = (
  network = "bluesky",
  provider?: string
): Promise<PipelineResponse> =>
  api
    .post<PipelineResponse>("/news/content", null, {
      params: { network, provider },
    })
    .then((r) => r.data);

export const processUrl = (
  req: ProcessUrlRequest
): Promise<PipelineResponse> =>
  api.post<PipelineResponse>("/news/process_url", req).then((r) => r.data);

export const getProcessUrlStatus = (jobId: string): Promise<PipelineResponse> =>
  api.get<PipelineResponse>(`/news/process_url/status/${jobId}`).then((r) => r.data);

export const runNewsPipeline = (): Promise<PipelineResponse> =>
  api.post<PipelineResponse>("/news/pipeline").then((r) => r.data);
