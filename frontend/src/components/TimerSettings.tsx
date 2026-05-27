import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Btn } from "./Btn";
import { Field } from "./Field";

interface TimerConfig {
  enabled: boolean;
  schedule_time: string;
  frequency: string;
}

interface TimerResponse {
  status: string;
  message: string;
  data?: Record<string, unknown>;
}

export function TimerSettings() {
  const [enabled, setEnabled] = useState(false);
  const [scheduleTime, setScheduleTime] = useState("08:00");
  const [frequency, setFrequency] = useState("daily");

  // Fetch current config
  const { data: configData, isLoading: configLoading, refetch: refetchConfig } = useQuery({
    queryKey: ["timer-config"],
    queryFn: async () => {
      const response = await api.get<TimerResponse>("/news/timer/config");
      return response.data.data as Record<string, unknown>;
    },
    staleTime: 30000,
  });

  // Fetch timer status
  const { data: statusData, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
    queryKey: ["timer-status"],
    queryFn: async () => {
      const response = await api.get<TimerResponse>("/news/timer/status");
      return response.data.data as Record<string, unknown>;
    },
    staleTime: 30000,
  });

  // Update config mutation
  const updateMutation = useMutation({
    mutationFn: async (config: TimerConfig) => {
      const response = await api.post<TimerResponse>("/news/timer/config", config);
      return response.data;
    },
    onSuccess: () => {
      refetchConfig();
      refetchStatus();
    },
  });

  // Update local state when config loads
  useEffect(() => {
    if (configData) {
      setEnabled((configData.enabled as boolean) ?? false);
      setScheduleTime((configData.schedule_time as string) ?? "08:00");
      setFrequency((configData.frequency as string) ?? "daily");
    }
  }, [configData]);

  const handleSave = () => {
    updateMutation.mutate({
      enabled,
      schedule_time: scheduleTime,
      frequency,
    });
  };

  const isActive = statusData?.active === true;

  return (
    <div className="space-y-4">
      <div className="bg-surface-card border border-surface-border rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm font-medium">Programación automática</p>
            <p className="text-xs text-gray-400">
              Ejecuta el pipeline automáticamente según la programación
            </p>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="w-5 h-5 accent-accent"
              disabled={configLoading}
            />
            <span className="text-sm font-medium">{enabled ? "Activo" : "Inactivo"}</span>
          </label>
        </div>

        {enabled && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Hora de ejecución"
                type="time"
                value={scheduleTime}
                onChange={(e) => setScheduleTime(e.target.value)}
                disabled={configLoading}
              />
              <div>
                <label className="block text-xs text-gray-400 mb-1">Frecuencia</label>
                <select
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value)}
                  disabled={configLoading}
                  className="w-full px-2 py-1.5 rounded bg-surface border border-surface-border text-xs text-gray-200 focus:outline-none focus:border-accent"
                >
                  <option value="daily">Diariamente</option>
                  <option value="weekly">Semanalmente</option>
                  <option value="hourly">Cada hora</option>
                </select>
              </div>
            </div>

            {/* Status info */}
            <div className="text-xs space-y-1 p-2 rounded bg-blue-950/20 border border-blue-800">
              <div>
                <span className="text-gray-400">Estado del timer: </span>
                <span className={isActive ? "text-green-400 font-medium" : "text-gray-400"}>
                  {isActive ? "✓ En ejecución" : "Detenido"}
                </span>
              </div>
              {statusData?.timers_output ? (
                <div className="text-gray-500 text-xs whitespace-pre-wrap max-h-16 overflow-y-auto">
                  {typeof statusData.timers_output === 'string' ? statusData.timers_output.split('\n')[1] : ''}
                </div>
              ) : null}
            </div>
          </div>
        )}

        <div className="flex gap-2 mt-4">
          <Btn
            loading={updateMutation.isPending || configLoading}
            onClick={handleSave}
            disabled={configLoading}
          >
            Guardar cambios
          </Btn>
          <Btn
            variant="ghost"
            loading={statusLoading}
            onClick={() => refetchStatus()}
            disabled={configLoading}
          >
            Actualizar estado
          </Btn>
        </div>

        {updateMutation.isError && (
          <div className="mt-3 p-2 rounded bg-red-950/40 border border-red-800">
            <p className="text-xs text-red-300">
              Error: {(updateMutation.error as Error)?.message || "No se pudo actualizar"}
            </p>
          </div>
        )}

        {updateMutation.isSuccess && (
          <div className="mt-3 p-2 rounded bg-green-950/40 border border-green-800">
            <p className="text-xs text-green-300">Cambios guardados correctamente</p>
          </div>
        )}
      </div>

      {/* Installation info */}
      <div className="bg-amber-950/20 rounded p-3 text-xs border border-amber-800 space-y-2">
        <p className="font-semibold text-amber-200">⚙️ Instalación</p>
        <p className="text-amber-300">
          Si no has instalado el timer systemd, ejecuta en la terminal:
        </p>
        <code className="block bg-gray-950 p-2 rounded text-gray-300 font-mono text-xs overflow-x-auto">
          bash ~/Public/news_bot_hex/scripts/install_timer.sh
        </code>
        <p className="text-amber-300 text-xs">
          Ver logs: <code className="bg-gray-950 px-1 rounded">journalctl --user -u news-bot-pipeline.service -f</code>
        </p>
      </div>
    </div>
  );
}
