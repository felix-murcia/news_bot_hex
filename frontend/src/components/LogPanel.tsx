import { useEffect, useState } from "react";
import { PipelineResponse } from "../api/client";
import { fetchLogTail } from "../api/logs";

interface LogPanelProps {
  response: PipelineResponse | null;
  error?: string | null;
  loading?: boolean;
}

export function LogPanel({ response, error, loading }: LogPanelProps) {
  const [liveLine, setLiveLine] = useState("");

  useEffect(() => {
    if (!loading) {
      setLiveLine("");
      return;
    }

    let cancelled = false;

    const poll = async () => {
      try {
        const lines = await fetchLogTail();
        if (!cancelled && lines.length > 0) {
          setLiveLine(lines[lines.length - 1]);
        }
      } catch {
        // silently ignore poll errors
      }
    };

    poll();
    const id = setInterval(poll, 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [loading]);

  if (loading) {
    return (
      <div className="mt-3 p-3 rounded-lg bg-surface border border-surface-border text-xs text-gray-400">
        <div className="flex items-center gap-2 mb-1">
          <span className="animate-spin inline-block w-3 h-3 border-2 border-accent border-t-transparent rounded-full flex-shrink-0" />
          Ejecutando…
        </div>
        {liveLine && (
          <p className="text-gray-500 truncate pl-5" title={liveLine}>
            {liveLine}
          </p>
        )}
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-3 p-3 rounded-lg bg-red-950/40 border border-red-800 text-xs text-red-300">
        <strong className="block mb-1">Error</strong>
        {error}
      </div>
    );
  }

  if (!response) return null;

  const isOk = response.status === "ok";

  return (
    <div
      className={`mt-3 p-3 rounded-lg border text-xs ${
        isOk
          ? "bg-green-950/30 border-green-800 text-green-300"
          : "bg-yellow-950/30 border-yellow-700 text-yellow-300"
      }`}
    >
      <strong className="block mb-1">{isOk ? "✓ " : "⚠ "}{response.message}</strong>
      {response.data && (
        <pre className="mt-2 text-gray-300 whitespace-pre-wrap break-all">
          {JSON.stringify(response.data, null, 2)}
        </pre>
      )}
    </div>
  );
}
