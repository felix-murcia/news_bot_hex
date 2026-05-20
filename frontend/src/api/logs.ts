import { api } from "./client";

export const fetchLogTail = (): Promise<string[]> =>
  api.get<{ lines: string[] }>("/logs/tail?lines=1").then((r) => r.data.lines);
