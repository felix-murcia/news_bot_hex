import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { StepCard } from "../../components/StepCard";
import { LogPanel } from "../../components/LogPanel";
import { Btn } from "../../components/Btn";
import { Field, SelectField } from "../../components/Field";
import { processAudio, runAudioPipeline } from "../../api/audio";
import { mutationState } from "../../api/mutationState";

const AI_PROVIDERS = [
  { label: "Default (settings)", value: "" },
  { label: "gemini", value: "gemini" },
  { label: "openai", value: "openai" },
  { label: "anthropic", value: "anthropic" },
];

export function AudioTab() {
  // Process
  const [url, setUrl] = useState("");
  const [provider, setProvider] = useState("");
  const [tema, setTema] = useState("Audios");
  const proc = useMutation({
    mutationFn: () =>
      processAudio({ url, provider: provider || undefined, tema }),
  });

  // Auto pipeline
  const [pipeUrl, setPipeUrl] = useState("");
  const [pipeTema, setPipeTema] = useState("Audios");
  const [noPublish, setNoPublish] = useState(false);
  const pipeline = useMutation({
    mutationFn: () =>
      runAudioPipeline({ url: pipeUrl, tema: pipeTema, no_publish: noPublish }),
  });

  return (
    <div>
      {/* Auto pipeline */}
      <div className="bg-surface-card border border-surface-border rounded-xl p-4 mb-6">
        <p className="text-sm font-medium mb-3">Pipeline automático de audio</p>
        <div className="grid grid-cols-1 gap-3 mb-3">
          <Field
            label="URL del audio"
            type="url"
            placeholder="https://youtube.com/watch?v=..."
            value={pipeUrl}
            onChange={(e) => setPipeUrl(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Tema"
              value={pipeTema}
              onChange={(e) => setPipeTema(e.target.value)}
            />
            <label className="flex items-center gap-2 text-xs text-gray-400 self-end pb-1">
              <input
                type="checkbox"
                checked={noPublish}
                onChange={(e) => setNoPublish(e.target.checked)}
                className="accent-accent"
              />
              Sin publicar
            </label>
          </div>
        </div>
        <Btn
          loading={pipeline.isPending}
          disabled={!pipeUrl}
          onClick={() => pipeline.mutate()}
          variant="ghost"
        >
          Ejecutar pipeline completo
        </Btn>
        <LogPanel {...mutationState(pipeline)} />
      </div>

      <hr className="border-surface-border my-6" />

      {/* STEP 1 – Process URL */}
      <StepCard
        step={1}
        title="Descargar y transcribir audio"
        description="Descarga el audio, transcribe y genera artículo + post."
      >
        <div className="grid grid-cols-1 gap-3 mb-3">
          <Field
            label="URL del audio (YouTube, Spotify, podcast…)"
            type="url"
            placeholder="https://youtube.com/watch?v=..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-3">
            <SelectField
              label="Proveedor IA"
              value={provider}
              onChange={setProvider}
              options={AI_PROVIDERS}
            />
            <Field
              label="Tema"
              value={tema}
              onChange={(e) => setTema(e.target.value)}
            />
          </div>
        </div>
        <Btn
          loading={proc.isPending}
          disabled={!url}
          onClick={() => proc.mutate()}
        >
          Procesar audio
        </Btn>
        <LogPanel {...mutationState(proc)} />
      </StepCard>
    </div>
  );
}
