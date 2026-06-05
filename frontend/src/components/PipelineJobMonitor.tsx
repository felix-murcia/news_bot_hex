import { useEffect, useState } from "react";
import { api } from "../api/client";
import { AlertCircle, CheckCircle, Clock } from "lucide-react";

interface PipelineStep {
  name: string;
  status: "running" | "ok" | "error" | "skipped" | "pending";
  timestamp?: string;
}

interface PipelineJob {
  id: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  message: string;
  steps: PipelineStep[];
  error?: string;
  last_log?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface PipelineJobMonitorProps {
  jobId: string;
  endpoint?: "pipeline" | "process_url";  // Specify which endpoint to poll (default: pipeline)
  onComplete?: (job: PipelineJob) => void;
  onError?: (error: string) => void;
}

function formatSeconds(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

export function PipelineJobMonitor({ jobId, endpoint = "pipeline", onComplete, onError }: PipelineJobMonitorProps) {
  const [job, setJob] = useState<PipelineJob | null>(null);
  const [isRunning, setIsRunning] = useState(true);

  useEffect(() => {
    if (!isRunning) return;

    const pollJob = async () => {
      try {
        const statusEndpoint = endpoint === "process_url" ? `/news/process_url/status/${jobId}` : `/news/pipeline/status/${jobId}`;
        const response = await api.get(statusEndpoint);
        const jobData = response.data.data as PipelineJob;
        setJob(jobData);

        // Stop polling when job completes
        if (jobData.status === "completed" || jobData.status === "failed") {
          setIsRunning(false);
          if (jobData.status === "completed") {
            onComplete?.(jobData);
          } else {
            const errorMsg = jobData.error || "Pipeline failed";
            onError?.(errorMsg);
          }
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Error fetching job status";
        setIsRunning(false);
        onError?.(errorMsg);
      }
    };

    // Poll immediately and then every 2 seconds
    pollJob();
    const interval = setInterval(pollJob, 2000);
    return () => clearInterval(interval);
  }, [jobId, isRunning, onComplete, onError]);

  if (!job) {
    return (
      <div className="mt-4 p-4 rounded-lg bg-surface border border-surface-border">
        <p className="text-sm text-gray-400">Inicializando pipeline...</p>
      </div>
    );
  }

  const getStepIcon = (status: string) => {
    switch (status) {
      case "ok":
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case "running":
        return <Clock className="w-5 h-5 text-blue-500 animate-spin" />;
      case "error":
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case "skipped":
        return <Clock className="w-5 h-5 text-gray-400" />;
      default:
        return <Clock className="w-5 h-5 text-gray-300" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "text-green-600";
      case "running":
        return "text-blue-600";
      case "failed":
        return "text-red-600";
      default:
        return "text-gray-600";
    }
  };

  return (
    <div className="space-y-4 mt-4 p-4 rounded-lg bg-surface border border-surface-border">
      {/* Status and Progress */}
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-gray-400 text-sm">Estado:</span>
          <span className={`font-semibold text-sm ${getStatusColor(job.status)}`}>
            {job.status === "pending" && "Pendiente"}
            {job.status === "running" && "En ejecución"}
            {job.status === "completed" && "✅ Completado"}
            {job.status === "failed" && "❌ Falló"}
          </span>
        </div>

        {/* Progress Bar */}
        <div className="space-y-1">
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-sm">Progreso:</span>
            <span className="font-semibold text-sm">{job.progress}%</span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                job.status === "failed" ? "bg-red-500" : "bg-green-500"
              }`}
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>

        {/* Message */}
        <p className="text-sm text-gray-400">{job.message}</p>

        {/* Error */}
        {job.error && (
          <div className="mt-2 text-sm text-red-400 bg-red-950/40 p-2 rounded">
            Error: {job.error}
          </div>
        )}
      </div>

      {/* Steps List */}
      <div className="space-y-2">
        <h3 className="font-semibold text-gray-300 text-sm">Pasos:</h3>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {job.steps.map((step) => (
            <div key={step.name} className="flex items-start gap-3 text-sm">
              {getStepIcon(step.status)}
              <div className="flex-1 pt-0.5">
                <div className="font-medium text-gray-200">{step.name}</div>
                {step.timestamp && (
                  <div className="text-xs text-gray-500">
                    {new Date(step.timestamp).toLocaleTimeString("es-ES")}
                  </div>
                )}
              </div>
              <div className="text-xs text-gray-500">
                {step.status === "ok" && "✓"}
                {step.status === "running" && "..."}
                {step.status === "error" && "✗"}
                {step.status === "skipped" && "⊘"}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Live Log Feedback */}
      {job.last_log && (
        <div className="space-y-1">
          <label className="text-xs font-mono text-gray-400">📝 Último evento:</label>
          <div className="bg-gray-950 rounded p-3 border border-gray-700">
            <p className="text-xs text-gray-300 font-mono break-words whitespace-pre-wrap max-h-24 overflow-y-auto">
              {job.last_log}
            </p>
          </div>
        </div>
      )}

      {/* Timing Info */}
      {job.started_at && (
        <div className={`rounded p-3 text-xs space-y-1 text-gray-300 border ${job.status === "failed" ? "bg-red-950/20 border-red-800" : "bg-blue-950/20 border-blue-800"}`}>
          <div>Iniciado: {new Date(job.started_at).toLocaleTimeString("es-ES")}</div>
          {job.completed_at && (
            <div>Completado: {new Date(job.completed_at).toLocaleTimeString("es-ES")}</div>
          )}
          {job.started_at && job.completed_at && (
            <div>
              Duración:{" "}
              {formatSeconds(
                Math.round(
                  (new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) /
                    1000
                )
              )}
            </div>
          )}
          {isRunning && job.started_at && (
            <div>
              Tiempo transcurrido:{" "}
              {formatSeconds(Math.round((Date.now() - new Date(job.started_at).getTime()) / 1000))}
            </div>
          )}
        </div>
      )}

      {/* Info Box */}
      <div className="bg-amber-950/20 rounded p-3 text-xs border border-amber-800">
        <div className="font-semibold text-amber-200 mb-2">ℹ️ Información</div>
        <ul className="text-amber-300 space-y-1 text-xs">
          <li>• El proceso completo puede tomar 6-17 minutos</li>
          <li>• La generación de audio (TTS) es lo más lento (5-10 min)</li>
          <li>• Los eventos de log aparecen en tiempo real arriba</li>
          <li>• Puedes dejar la pestaña en background</li>
        </ul>
      </div>
    </div>
  );
}
