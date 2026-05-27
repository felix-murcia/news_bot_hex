import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { StepCard } from "../../components/StepCard";
import { LogPanel } from "../../components/LogPanel";
import { PipelineJobMonitor } from "../../components/PipelineJobMonitor";
import { Btn } from "../../components/Btn";
import { Field, SelectField } from "../../components/Field";
import {
  fetchRss,
  listRssArticles,
  verifyNews,
  softVerify,
  generateArticle,
  generateContent,
  processUrl,
  runNewsPipeline,
  getSupportedProviders,
} from "../../api/news";
import { mutationState } from "../../api/mutationState";

const DEFAULT_AI_PROVIDERS = [
  { label: "Default (settings)", value: "" },
  { label: "gemini", value: "gemini" },
  { label: "openai", value: "openai" },
  { label: "anthropic", value: "anthropic" },
];

const NETWORKS = [
  { label: "Bluesky", value: "bluesky" },
  { label: "Twitter / X", value: "twitter" },
  { label: "Mastodon", value: "mastodon" },
  { label: "Facebook", value: "facebook" },
];

const PIPELINE_JOB_KEY = "news-pipeline-job-id";

export function NewsTab() {
  // Fetch supported providers on mount
  const [aiProviders, setAiProviders] = useState(DEFAULT_AI_PROVIDERS);

  useEffect(() => {
    getSupportedProviders()
      .then((data) => {
        const providers = [
          { label: "Default (settings)", value: "" },
          ...data.providers.map((p) => ({
            label: p,
            value: p,
          })),
        ];
        setAiProviders(providers);
      })
      .catch(() => {
        // Fallback to defaults if fetch fails
        setAiProviders(DEFAULT_AI_PROVIDERS);
      });
  }, []);

  // Pipeline Job Monitor state - recover from localStorage if exists
  const [pipelineJobId, setPipelineJobId] = useState<string | null>(() => {
    // Try to restore job_id from localStorage on mount
    try {
      return localStorage.getItem(PIPELINE_JOB_KEY);
    } catch {
      return null;
    }
  });

  // Persist/clear job_id in localStorage
  useEffect(() => {
    if (pipelineJobId) {
      try {
        localStorage.setItem(PIPELINE_JOB_KEY, pipelineJobId);
      } catch {
        // Silently ignore localStorage errors
      }
    } else {
      try {
        localStorage.removeItem(PIPELINE_JOB_KEY);
      } catch {
        // Silently ignore localStorage errors
      }
    }
  }, [pipelineJobId]);

  // Step 1 – RSS
  const [articlesOpen, setArticlesOpen] = useState(false);
  const [dateOrder, setDateOrder] = useState<"asc" | "desc">("desc");

  const articles = useQuery({
    queryKey: ["rss-articles"],
    queryFn: listRssArticles,
    // Only fetch when the user opens the collapsible
    enabled: articlesOpen,
    staleTime: 0,
  });

  const rss = useMutation({
    mutationFn: fetchRss,
    onSuccess: () => {
      // Refetch the list after a new fetch so it's up to date
      articles.refetch();
    },
  });

  // Step 2 – Verify
  const verify = useMutation({ mutationFn: verifyNews });
  const soft = useMutation({ mutationFn: softVerify });

  // Step 3 – Article / Content
  const [articleProvider, setArticleProvider] = useState("");
  const [articleLimit, setArticleLimit] = useState("1");
  const article = useMutation({
    mutationFn: () =>
      generateArticle(articleProvider || undefined, Number(articleLimit)),
  });

  const [network, setNetwork] = useState("bluesky");
  const [contentProvider, setContentProvider] = useState("");
  const content = useMutation({
    mutationFn: () => generateContent(network, contentProvider || undefined),
  });

  // Step 4 – Process a specific URL
  const [processUrlValue, setProcessUrlValue] = useState("");
  const [processProvider, setProcessProvider] = useState("");
  const [useAi, setUseAi] = useState(true);
  const [forceExtract, setForceExtract] = useState(false);
  const urlProc = useMutation({
    mutationFn: () =>
      processUrl({
        url: processUrlValue,
        provider: processProvider || undefined,
        use_ai: useAi,
        force_extract: forceExtract,
      }),
  });

  // Auto pipeline
  const pipeline = useMutation({
    mutationFn: runNewsPipeline,
    onSuccess: (data) => {
      // Extract job_id from response data
      const jobId = data.data?.job_id as string | undefined;
      if (jobId) {
        setPipelineJobId(jobId);
      }
    },
  });

  return (
    <div>
      {/* Auto pipeline banner */}
      <div className="bg-surface-card border border-surface-border rounded-xl p-4 mb-6 flex items-center gap-4">
        <div className="flex-1">
          <p className="text-sm font-medium">Pipeline automático</p>
          <p className="text-xs text-gray-400">
            Ejecuta el pipeline completo de noticias en un solo paso.
          </p>
        </div>
        <Btn
          loading={pipeline.isPending || !!pipelineJobId}
          onClick={() => {
            setPipelineJobId(null);
            pipeline.mutate();
          }}
          variant="ghost"
          disabled={!!pipelineJobId}
        >
          Ejecutar pipeline
        </Btn>
      </div>

      {/* Pipeline Job Monitor (shows real-time feedback) */}
      {pipelineJobId && (
        <PipelineJobMonitor
          jobId={pipelineJobId}
          onComplete={() => setPipelineJobId(null)}
          onError={() => setPipelineJobId(null)}
        />
      )}

      {/* Fallback error display */}
      {pipeline.isError && !pipelineJobId && (
        <div className="mt-4 p-4 rounded-lg bg-red-950/40 border border-red-800">
          <p className="text-sm font-semibold text-red-300 mb-1">Error al iniciar pipeline</p>
          <p className="text-xs text-red-400">
            {pipeline.error instanceof Error ? pipeline.error.message : "Error desconocido"}
          </p>
        </div>
      )}

      <hr className="border-surface-border my-6" />

      {/* STEP 1 – RSS */}
      <StepCard
        step={1}
        title="Fetch RSS"
        description="Descarga y almacena los artículos RSS en MongoDB."
      >
        <div className="flex items-center gap-3 flex-wrap">
          <Btn loading={rss.isPending} onClick={() => rss.mutate()}>
            Fetch RSS
          </Btn>
          <button
            onClick={() => {
              setArticlesOpen((o) => !o);
            }}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-200 transition-colors"
          >
            <span
              className={`inline-block transition-transform duration-200 ${articlesOpen ? "rotate-90" : ""}`}
            >
              ▶
            </span>
            {articlesOpen ? "Ocultar artículos" : "Ver artículos almacenados"}
          </button>
        </div>

        {/* Collapsible article list */}
        {articlesOpen && (
          <div className="mt-4">
            {articles.isLoading && (
              <p className="text-xs text-gray-400 flex items-center gap-2">
                <span className="animate-spin inline-block w-3 h-3 border-2 border-accent border-t-transparent rounded-full" />
                Cargando…
              </p>
            )}
            {articles.error && (
              <p className="text-xs text-red-400">
                Error al cargar: {String((articles.error as Error).message)}
              </p>
            )}
            {articles.data && articles.data.length === 0 && (
              <p className="text-xs text-gray-500 italic">
                No hay artículos almacenados. Haz Fetch RSS primero.
              </p>
            )}
            {articles.data && articles.data.length > 0 && (
              <div className="overflow-x-auto overflow-y-auto max-h-72 rounded-lg border border-surface-border">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-surface-border bg-surface">
                      <th className="text-left px-3 py-2 text-gray-400 font-medium">Título</th>
                      <th className="text-left px-3 py-2 text-gray-400 font-medium w-32">Fuente</th>
                      <th className="text-left px-3 py-2 text-gray-400 font-medium w-36">
                        <button
                          onClick={() => setDateOrder((o) => (o === "desc" ? "asc" : "desc"))}
                          className="flex items-center gap-1 hover:text-gray-200 transition-colors"
                        >
                          Fecha
                          <span>{dateOrder === "desc" ? "↓" : "↑"}</span>
                        </button>
                      </th>
                      <th className="px-3 py-2 w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {[...articles.data]
                      .sort((a, b) => {
                        const ta = a.publishedAt ? new Date(a.publishedAt).getTime() : 0;
                        const tb = b.publishedAt ? new Date(b.publishedAt).getTime() : 0;
                        return dateOrder === "desc" ? tb - ta : ta - tb;
                      })
                      .map((a, i) => (
                      <tr
                        key={i}
                        className="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                      >
                        <td className="px-3 py-2 text-gray-200">{a.title || "—"}</td>
                        <td className="px-3 py-2 text-gray-400 truncate max-w-[8rem]">{a.source || "—"}</td>
                        <td className="px-3 py-2 text-gray-400">
                          {a.publishedAt
                            ? new Date(a.publishedAt).toLocaleString("es-ES", {
                                day: "2-digit",
                                month: "2-digit",
                                year: "2-digit",
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : "—"}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <a
                            href={a.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            title={a.url}
                            className="text-accent hover:text-white transition-colors"
                          >
                            ↗
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-right text-gray-600 text-xs px-3 py-1.5">
                  {articles.data.length} artículo{articles.data.length !== 1 ? "s" : ""}
                </p>
              </div>
            )}
          </div>
        )}

        <LogPanel {...mutationState(rss)} />
      </StepCard>

      {/* STEP 2 – Verify */}
      <StepCard
        step={2}
        title="Verificación / Scoring"
        description="Puntúa y filtra las noticias almacenadas."
      >
        <div className="flex gap-2 flex-wrap">
          <Btn loading={verify.isPending} onClick={() => verify.mutate()}>
            Verificación completa
          </Btn>
          <Btn
            loading={soft.isPending}
            onClick={() => soft.mutate()}
            variant="ghost"
          >
            Verificación soft
          </Btn>
        </div>
        <LogPanel {...mutationState(verify)} />
        <LogPanel {...mutationState(soft)} />
      </StepCard>

      {/* STEP 3a – Article */}
      <StepCard
        step={3}
        title="Generar artículo"
        description="Genera artículos profesionales desde las noticias verificadas."
      >
        <div className="grid grid-cols-2 gap-3 mb-3">
          <SelectField
            label="Proveedor IA"
            value={articleProvider}
            onChange={setArticleProvider}
            options={aiProviders}
          />
          <Field
            label="Límite de artículos"
            type="number"
            min={1}
            max={20}
            value={articleLimit}
            onChange={(e) => setArticleLimit(e.target.value)}
          />
        </div>
        <Btn loading={article.isPending} onClick={() => article.mutate()}>
          Generar artículo
        </Btn>
        <LogPanel {...mutationState(article)} />
      </StepCard>

      {/* STEP 3b – Social content */}
      <StepCard
        step={4}
        title="Generar contenido para redes sociales"
        description="Genera posts para la red seleccionada desde las noticias verificadas."
      >
        <div className="grid grid-cols-2 gap-3 mb-3">
          <SelectField
            label="Red social"
            value={network}
            onChange={setNetwork}
            options={NETWORKS}
          />
          <SelectField
            label="Proveedor IA"
            value={contentProvider}
            onChange={setContentProvider}
            options={aiProviders}
          />
        </div>
        <Btn loading={content.isPending} onClick={() => content.mutate()}>
          Generar posts
        </Btn>
        <LogPanel {...mutationState(content)} />
      </StepCard>

      {/* STEP 5 – Process URL */}
      <StepCard
        step={5}
        title="Procesar URL concreta"
        description="Extrae contenido, genera artículo y tweet desde una URL de noticia."
      >
        <div className="grid grid-cols-1 gap-3 mb-3">
          <Field
            label="URL de la noticia"
            type="url"
            placeholder="https://ejemplo.com/noticia"
            value={processUrlValue}
            onChange={(e) => setProcessUrlValue(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-3">
            <SelectField
              label="Proveedor IA"
              value={processProvider}
              onChange={setProcessProvider}
              options={aiProviders}
            />
            <div className="flex flex-col gap-2">
              <label className="flex items-center gap-2 text-xs text-gray-400">
                <input
                  type="checkbox"
                  checked={useAi}
                  onChange={(e) => setUseAi(e.target.checked)}
                  className="accent-accent"
                />
                Usar IA
              </label>
              <label className="flex items-center gap-2 text-xs text-gray-400">
                <input
                  type="checkbox"
                  checked={forceExtract}
                  onChange={(e) => setForceExtract(e.target.checked)}
                  className="accent-accent"
                />
                Forzar extracción con Jina
              </label>
            </div>
          </div>
        </div>
        <Btn
          loading={urlProc.isPending}
          disabled={!processUrlValue}
          onClick={() => urlProc.mutate()}
        >
          Procesar URL
        </Btn>
        <LogPanel {...mutationState(urlProc)} />
      </StepCard>
    </div>
  );
}
