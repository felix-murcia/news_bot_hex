import axios from "axios";

// In dev, Vite proxies /api → localhost:8000 (strips /api prefix)
// In Docker, VITE_API_BASE_URL is set to http://backend:8000
// The nginx container serves static files and proxies /api to the backend
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 0, // no timeout — pipelines can run for many minutes
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": import.meta.env.VITE_APP_API_KEY ?? "",
  },
});

// Shared response shape from all backend endpoints
export interface PipelineResponse {
  status: string;
  message: string;
  data?: Record<string, unknown>;
}
