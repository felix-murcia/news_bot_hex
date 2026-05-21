/**
 * PipelineAutomaticoTab - Pestaña "Pipeline Automático" para ejecutar y monitorear el pipeline completo
 *
 * Uso:
 * - El usuario hace clic en "Ejecutar Pipeline"
 * - Se inicia el proceso en background (devuelve job_id)
 * - El frontend hace polling cada 2 segundos para actualizaciones
 * - Se muestra progreso en tiempo real
 */

import React, { useState, useEffect, useRef } from 'react';
import { Play, RotateCcw, CheckCircle, AlertCircle, Clock } from 'lucide-react';

interface PipelineStep {
  name: string;
  status: 'running' | 'ok' | 'error' | 'skipped' | 'pending';
  timestamp?: string;
}

interface PipelineJob {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
  steps: PipelineStep[];
  error?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

const PipelineAutomaticoTab: React.FC = () => {
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<PipelineJob | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Iniciar pipeline
  const startPipeline = async () => {
    try {
      setError(null);
      setIsRunning(true);

      const response = await fetch('/api/pipeline', {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`Error iniciando pipeline: ${response.statusText}`);
      }

      const data = await response.json();
      const newJobId = data.data.job_id;
      setJobId(newJobId);

      // Iniciar polling
      pollPipelineStatus(newJobId);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Error desconocido';
      setError(errorMessage);
      setIsRunning(false);
    }
  };

  // Polling para obtener estado
  const pollPipelineStatus = async (id: string) => {
    // Limpiar intervalo anterior si existe
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    // Crear nuevo intervalo de polling
    pollingIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(`/api/pipeline/status/${id}`);

        if (!response.ok) {
          if (response.status === 404) {
            setError('Job no encontrado');
            setIsRunning(false);
            if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
            return;
          }
          throw new Error(`Error: ${response.statusText}`);
        }

        const data = await response.json();
        const jobData = data.data as PipelineJob;
        setJob(jobData);

        // Detener polling si completó
        if (jobData.status === 'completed' || jobData.status === 'failed') {
          setIsRunning(false);
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
          }
        }
      } catch (err) {
        console.error('Error en polling:', err);
        // Continuar intentando aunque hay error
      }
    }, 2000); // Polling cada 2 segundos
  };

  // Detener polling al desmontar
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  const getStepIcon = (status: string) => {
    switch (status) {
      case 'ok':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'running':
        return <Clock className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'skipped':
        return <Clock className="w-5 h-5 text-gray-400" />;
      default:
        return <Clock className="w-5 h-5 text-gray-300" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600';
      case 'running':
        return 'text-blue-600';
      case 'failed':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className="space-y-6 p-6 bg-white dark:bg-gray-900 rounded-lg">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Pipeline Automático</h2>
        <button
          onClick={startPipeline}
          disabled={isRunning}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold transition-all ${
            isRunning
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 text-white'
          }`}
        >
          <Play className="w-5 h-5" />
          {isRunning ? 'Ejecutando...' : 'Ejecutar Pipeline'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-red-800 dark:text-red-200">Error</h3>
              <p className="text-red-700 dark:text-red-300">{error}</p>
            </div>
          </div>
        </div>
      )}

      {job && (
        <div className="space-y-4">
          {/* Job Info */}
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Estado:</span>
              <span className={`font-semibold ${getStatusColor(job.status)}`}>
                {job.status === 'pending' && 'Pendiente'}
                {job.status === 'running' && 'En ejecución'}
                {job.status === 'completed' && '✅ Completado'}
                {job.status === 'failed' && '❌ Falló'}
              </span>
            </div>

            {/* Progress Bar */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-gray-600 dark:text-gray-400">Progreso:</span>
                <span className="font-semibold">{job.progress}%</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${
                    job.status === 'failed' ? 'bg-red-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${job.progress}%` }}
                />
              </div>
            </div>

            <div className="text-sm text-gray-600 dark:text-gray-400">
              {job.message}
            </div>

            {job.error && (
              <div className="text-sm text-red-600 dark:text-red-400 mt-2">
                Error: {job.error}
              </div>
            )}
          </div>

          {/* Steps Timeline */}
          <div className="space-y-3">
            <h3 className="font-semibold text-gray-700 dark:text-gray-300">Pasos:</h3>
            <div className="space-y-2">
              {job.steps.map((step, idx) => (
                <div key={step.name} className="flex items-start gap-3">
                  {getStepIcon(step.status)}
                  <div className="flex-1 pt-0.5">
                    <div className="font-medium text-gray-800 dark:text-gray-200">
                      {step.name}
                    </div>
                    {step.timestamp && (
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {new Date(step.timestamp).toLocaleTimeString()}
                      </div>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {step.status === 'ok' && '✓'}
                    {step.status === 'running' && 'En progreso...'}
                    {step.status === 'error' && 'Error'}
                    {step.status === 'skipped' && 'Saltado'}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Timing Info */}
          {job.started_at && (
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 text-sm">
              <div className="space-y-1 text-gray-700 dark:text-gray-300">
                <div>Iniciado: {new Date(job.started_at).toLocaleTimeString()}</div>
                {job.completed_at && (
                  <div>
                    Completado: {new Date(job.completed_at).toLocaleTimeString()}
                  </div>
                )}
                {job.started_at && job.completed_at && (
                  <div>
                    Duración:{' '}
                    {Math.round(
                      (new Date(job.completed_at).getTime() -
                        new Date(job.started_at).getTime()) /
                        1000
                    )}{' '}
                    segundos
                  </div>
                )}
                {isRunning && job.started_at && (
                  <div>
                    Tiempo transcurrido:{' '}
                    {Math.round((Date.now() - new Date(job.started_at).getTime()) / 1000)}{' '}
                    segundos
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Info Box */}
          <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4 text-sm">
            <div className="font-semibold text-amber-800 dark:text-amber-200 mb-2">
              ℹ️ Información
            </div>
            <ul className="text-amber-700 dark:text-amber-300 space-y-1 text-xs">
              <li>• El proceso completo puede tomar 6-17 minutos</li>
              <li>• La generación de audio (TTS) es lo más lento (5-10 min)</li>
              <li>• No cierres esta pestaña mientras está en progreso</li>
              <li>• Puedes dejar la pestaña en background</li>
            </ul>
          </div>
        </div>
      )}

      {!job && !isRunning && (
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-6 text-center">
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Haz clic en "Ejecutar Pipeline" para iniciar el proceso completo de:
          </p>
          <ul className="text-gray-600 dark:text-gray-400 text-sm space-y-2 mb-4">
            <li>✓ Fetch de noticias RSS</li>
            <li>✓ Verificación y scoring</li>
            <li>✓ Generación de posts/tweets</li>
            <li>✓ Generación de artículos profesionales</li>
            <li>✓ Búsqueda de imágenes</li>
            <li>✓ <strong>Transcripción a audio (TTS Coqui)</strong></li>
            <li>✓ Generación de videos</li>
            <li>✓ Publicación en WordPress y redes sociales</li>
          </ul>
        </div>
      )}
    </div>
  );
};

export default PipelineAutomaticoTab;
