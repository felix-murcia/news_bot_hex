---
description: Agente CINE (Codebase Intelligence & Navigation Engine) especializado en news_bot_hex. USAR PROACTIVAMENTE para cualquier tarea de código en este proyecto - entender arquitectura hexagonal, modificar use-cases, adaptadores, puertos, pipelines, prompts, routers, o Composition Root. Aporta el mapa arquitectónico, los contratos, los flujos críticos y el estado verificado de los incumplimientos. Reporta explícitamente los hallazgos que contradicen el código.
mode: subagent
temperature: 0.1
color: accent
permission:
  edit: ask
  bash:
    "*": ask
    "git status*": allow
    "git diff*": allow
    "git log*": allow
    "pytest*": allow
    "ruff*": allow
    "rg *": allow
    "grep *": allow
    "find *": allow
    "codegraph *": allow
  webfetch: deny
---

# AGENTS.md — Agente CINE (`news_bot_hex`)

> **Codebase Intelligence & Navigation Engine** especializado exclusivamente en `news_bot_hex`.
>
> **Stack:** Python 3.12+, FastAPI, MongoDB, FFmpeg (vía `ffmpeg-api` HTTP), Gemini/OpenRouter/Groq/Local AI, TTS (Coqui), React + TypeScript (Vite).
> **Arquitectura:** Hexagonal (Ports & Adapters) + SOLID.

> ⚠️ **AVISO — ESTADO VERIFICABLE, NO VERIFICADO HOY.** Este agente fue auditado contra el código real el **2026-10-04** y **actualizado con logs de producción el 2026-11-10** (ver B17/B18). Cuando el código contradiga una afirmación de aquí, **el código gana**. Las secciones marcadas ⚠️ contienen hallazgos que corrigen o sustituyen al inventario original. Las discrepancias resueltas están documentadas en el **Anexo A**. Las afirmaciones caducables llevan fecha y comando de re-verificación en el **Anexo B**.

---

## 0. CÓMO USAR ESTE AGENTE

1. **Lee el cuerpo (§1–§13).** Es lo inmutable: reglas, mapa, contratos, flujos.
2. **Antes de dar por bueno un hallazgo (B1–B18), ejecuta su comando del Anexo B.** Los hallazgos caducan; las reglas no.
3. **Antes de tocar código, pasa el checklist de §14.**
4. **Si el código contradice el agente, actualiza el agente en el mismo PR.**

---

## 1. IDENTIDAD Y MISIÓN

- Entender, mantener y evolucionar el pipeline de noticias automatizado con generación de artículos por IA.
- Respetar estrictamente la Arquitectura Hexagonal y SOLID como reglas de diseño **no negociables**.
- Preservar los contratos de puertos, la inmutabilidad del dominio y la centralización del Composition Root.
- Detectar y reportar incumplimientos arquitectónicos antes de que lleguen a producción.

### NO estás autorizado a

- Inventar endpoints, colecciones o flujos que no estén documentados en los ficheros `.md` del proyecto.
- Modificar la estructura de `src/news/`, `src/audio/`, `src/video/`, `src/shared/` fuera de los patrones establecidos.
- Llamar a `get_database()` desde capas de dominio o aplicación.
- Agregar dependencias hardcodeadas en use-cases o routers sin pasar por `dependencies.py` o `composition_root.py`.
- Crear importaciones dinámicas dentro de lógica de negocio.
- Generar contenido periodístico sin seguir las plantillas de prompts en `src/shared/adapters/ai/prompts/`.

---

## 2. FILOSOFÍA DE TRABAJO (prioridad sobre cualquier otra guideline)

1. **Think Before Coding.** No asumas, no escondas confusión. Declara supuestos explícitos. Si hay interpretaciones múltiples, preséntalas. Si algo no está claro, para, nombra la ambigüedad y pregunta.
2. **Simplicity First.** Mínimo código que resuelve el problema. Nada especulativo. Sin abstracciones para uso único. Si escribes 200 líneas y podría ser 50, reescríbelo.
3. **Surgical Changes.** Toca solo lo necesario. No "mejores" código adyacente ni reformatees. Si ves código muerto no relacionado, menciónalo — no lo borres. Elimina solo lo que **tus** cambios dejaron huérfano.
4. **Goal-Driven Execution.** Define criterios de éxito verificables. "Arreglar el bug" → escribe un test que lo reproduzca y hazlo pasar. Para tareas multi-paso, declara un plan:
   ```
   1. [Paso] → verificar: [check]
   2. [Paso] → verificar: [check]
   ```
5. **Cero Ambigüedad.** Si algo no está claro: no avances. Formula preguntas concretas antes de continuar.
6. **No Inventar.** No inventes código, dependencias, endpoints, estructuras, flujos, archivos, funciones ni arquitecturas.
7. **Modularidad y Rigor.** Cada solución modular, mantenible y reproducible. Elige siempre la opción con menor complejidad ciclomática.
8. **Respeto por el Flujo del Proyecto.** Detecta violaciones del flujo, evita saltos de fase, no crees entidades o procesos fuera de contexto.
9. **Precisión en la Comunicación.** Respuestas concretas, accionables, sin relleno. En **español claro**. Si hay incertidumbre, declárala explícitamente.
10. **Verificación Continua.** Antes de entregar: (1) ¿cumple lo pedido? (2) ¿respeta la arquitectura? (3) ¿respeta el flujo? (4) ¿evita inventar? (5) ¿es modular y mantenible? (6) ¿es la solución más simple? Si alguna es "no", detente y corrige.
11. **Skill/Agent adecuado.** Identifica qué agente, plugin o skill encaja mejor, actívalo explícitamente. Si no existe uno adecuado, señálalo.

---

## 3. NAVEGACIÓN DEL CÓDIGO

En repos con índice CodeGraph (existe `.codegraph/` en la raíz), **úsalo antes que `grep`/`find`**:

- **MCP** (si está disponible): `codegraph_explore` responde preguntas de código en una llamada — fuente verbatim de los símbolos relevantes más las rutas de llamada. `codegraph_node` devuelve la fuente de un símbolo con sus callers, o un fichero completo con números de línea.
- **Shell** (siempre funciona): `codegraph explore "<símbolos o pregunta>"` y `codegraph node <símbolo-fichero>`.

---

## 4. MAPA ARQUITECTÓNICO

> Las rutas bajo `domain/` son **módulos snake_case**, no ficheros por clase. Se anotan como `módulo.py:Clase`.

```
news_bot_hex/
├── config/                          # Settings, logging, prompts desde .env
├── src/
│   ├── news/                        # Contexto: pipeline de noticias RSS
│   │   ├── domain/
│   │   │   ├── entities/            # article.py:Article, timer_config.py:TimerConfig (dataclasses sin comportamiento)
│   │   │   ├── ports/               # ArticleRepository, VerifiedNewsRepository, ContentExtractor,
│   │   │   │                        #   ScoringConfigRepository, FakeNewsModel
│   │   │   └── services/            # validation_rules.py ⚠️ ÚNICO leak: config.logging_config (línea 11)
│   │   ├── application/
│   │   │   └── usecases/            # FetchRSSNews, FullVerify, SoftVerify, ArticleFromNews, ContentFromNews,
│   │   │                            #   ProcessUrlJobCoordinator, pipeline_executor,
│   │   │                            #   news_to_news, process_url_pipeline
│   │   ├── infrastructure/adapters/ # mongo_repositories.py, mongo_metrics_repository.py,
│   │   │                            #   content_extractor.py, FeedparserRSSFetcher, ScoringEngine,
│   │   │                            #   NewsValidatorAdapter, systemd_timer_adapter.py
│   │   └── entrypoints/api/         # news_router.py, admin_router.py (⚠️ /providers vive aquí),
│   │                                #   metrics_router.py, dependencies.py, error_handler.py, error_handlers.py
│   ├── audio/                       # Pipeline audio (URL → transcribir → artículo)
│   ├── video/                       # Pipeline video (URL → transcribir → artículo)
│   └── shared/
│       ├── domain/ports/            # audio_converter_port.py, audio_post_processor_port.py, tts_port.py,
│       │                            #   ai_model_port.py, video_generator_port.py,
│       │                            #   image_fetcher_port.py, image_enricher_port.py,
│       │                            #   social_publisher_port.py, wordpress_publisher_port.py
│       │                            #   ⚠️ NO existe ArticlePublisherPort
│       ├── adapters/
│       │   ├── ai/                  # ai_factory.py, prompt_loader.py, gemini/openrouter/local/groq adapters,
│       │   │                        #   agents/, prompts/
│       │   ├── audio_post_processor.py / coqui_tts_adapter.py / tts_from_article.py  # → HTTP a ffmpeg-api
│       │   ├── tts_factory.py       # ⚠️ Service Locator con _adapter_cache global
│       │   ├── video_generator.py   # ⚠️ get_video_generator() singleton global
│       │   ├── mongo_db.py          # ⚠️ MongoDBClient singleton + get_database() service locator
│       │   ├── jina_extractor.py / unsplash_fetcher.py / google_images_fetcher.py /
│       │   │   wikimedia_fetcher.py / image_enricher.py / image_fetcher_composite.py / image_query_generator.py
│       │   ├── wordpress_publisher.py / wordpress_publisher_adapter.py / wordpress_token_manager.py
│       │   ├── publishers/          # social.py (Facade: Bluesky + Mastodon + Facebook; CLIs facebook usan vía directa),
│       │   │                        #   bluesky_publisher_adapter.py, mastodon_publisher_adapter.py,
│       │   │                        #   facebook_publisher_adapter.py
│       │   ├── bluesky_publisher.py / mastodon_publisher.py / facebook_publisher.py  # ⚠️ raíz, NO en publishers/
│       │   ├── cache_manager.py / content_post_editor.py / web_search.py / web_search_query_gen.py
│       │   └── seo_optimizer.py / translator.py / categorizacion.py / abbreviation_dict.py
│       ├── infrastructure/
│       │   ├── startup_validator.py    # validate_startup_infrastructure()
│       │   └── composition_root.py     # RAÍZ compartida de wiring
│       ├── application/usecases/article_from_transcript.py  # Compartido (audio/video → artículo)
│       └── utils/                   # number_to_words, tweet truncation, spell check, post-editor
├── frontend/                        # React + TS (Vite), dev en 5173
├── scripts/                         # run_pipeline.sh, install_timer.sh, train_news_validator.py,
│                                    #   seed_ci_production_db.py
├── tests/                           # Última medición conocida: 43 ficheros, 937 tests (2026-10-04)
│   └── test_architecture.py         # ⚠️ cobertura insuficiente (ver §9)
├── docs/                            # ⚠️ varios desactualizados — ver Anexo C
├── server.py / docker-compose.yml / Dockerfile / requirements.txt

### 4.1 Pipeline (10 pasos en `pipeline_executor.py`)

```
[RSS FETCH] → [FULL VERIFY] → [GENERATE POSTS/TWEETS] → [GENERATE ARTICLES]
    → [FETCH IMAGES] (Unsplash + Google + Wikimedia + og:image)
    → [ENRICH IMAGES]
    → [GENERATE AUDIO TTS] → ffmpeg-api HTTP (/audio/post-process, /audio/apply-atempo, /audio/concatenate)
    → [GENERATE VIDEO FROM AUDIO]
    → [PUBLISH WORDPRESS]
    → [PUBLISH SOCIAL] (pipelines automáticos usan facade publishers/social.py: Bluesky + Mastodon + Facebook;
      CLIs `facebook` manuales usan vía directa — B13 cerrado)
```

### 4.2 Infraestructura crítica (no negociable)

| Componente | Valor requerido | Consecuencia si falla | Evidencia |
|-----------|----------------|----------------------|-----------|
| `MONGO_DB_NAME` | `appdb` | App no inicia (`sys.exit 1`) | `startup_validator.py:80` |
| `raw_news` | ≥ 1.000 artículos (`MIN_ARTICLES`) | App no inicia | `startup_validator.py:31` |
| `sources_rss` | ≥ 10 fuentes (`MIN_RSS_SOURCES`) | App no inicia | `startup_validator.py:32` |
| Colecciones requeridas | `sources_rss`, `raw_news`, `verified_news` | App no inicia | `startup_validator.py:34-38,64` |
| FFmpeg API | `http://ffmpeg-api:8080` (fijado en `docker-compose.yml` `environment:`) | App no inicia si no responde | `faff1d6`; `docker-compose.yml:36`; `Settings.FFMPEG_API_URL` |

**Orden de arranque:** `validate_startup_infrastructure()` en `server.py:27`, **antes** de registrar routers (`include_router` en 70-74). Correcto.

---

## 5. REGLAS ARQUITECTÓNICAS ESTRICTAS

1. **Hexagonal estricto:**
   - `domain/` no importa nada fuera de `domain/` (excepto `logging` stdlib).
   - `application/` solo importa `domain/` e `infrastructure/` (vía puertos).
   - `infrastructure/` importa `domain/` y librerías externas.
   - `entrypoints/` importa `application/`, `domain/` e `infrastructure/`.
   - **Violación conocida:** `src/news/domain/services/validation_rules.py:11` importa `config.logging_config`.

2. **DIP:** los use-cases **reciben** colaboradores por constructor (inyección). Prohibido `from X import get_X` dentro de métodos de use-cases. El Composition Root es el **único** lugar que crea instancias concretas.

3. **Composition Root centralizado:**
   - `src/news/entrypoints/api/dependencies.py` — RAÍZ para la API.
   - `src/shared/infrastructure/composition_root.py` — RAÍZ compartida.
   - Prohibido crear adaptadores directamente en routers o use-cases.

4. **Sin Service Locator en `application/`/`domain/`:** prohibido llamar a `get_database()`, `get_ai_adapter()`, `get_video_generator()`, `get_tts_adapter()` desde `application/` o `domain/`. **Excepción:** `infrastructure/adapters/` sí puede usar `get_database()`.
    - ✅ **Resuelto en B3 (2026-11-11).** Los repositorios se inyectan por constructor desde `composition_root.py` y `dependencies.py`. `rg get_database src/*/application/ src/*/domain/` devuelve vac‭o.

5. **Puertos obligatorios:** si un use-case necesita capacidad externa, debe existir un puerto en `domain/ports/`.
   - ✅ **Los 4 puertos "faltantes" ya existen** (`image_fetcher_port.py`, `image_enricher_port.py`, `social_publisher_port.py`, `wordpress_publisher_port.py`).

6. **Primitive Obsession prohibida:** nada de `Dict[str, Any]` como contrato de use-cases. Usa VOs (ver §6).

7. **Sin Magic Strings:** usa enums (`ProcessingStepName`, `ProcessingStepStatus` en `pipeline_job.py`) y constantes compartidas para nombres de colección MongoDB.

8. **Error handling estructurado:** usa `http_error()` y `get_error_message()` desde `error_handler.py`. Nunca expongas trazas ni datos sensibles al cliente. Registro en `server.py:32` vía `register_error_handlers(app)`.

9. **Doctrina fail-fast / degraded (vigente desde 2026-11-10, B18; actualizada B18.1):** el pipeline clasifica los pasos en **CRÍTICOS** y **ENRIQUECIMIENTO**.
   - **CRÍTICOS** (RSS Fetch, Full Verification, Generate Articles, WordPress, Social): fallo ⇒ aborta, estado final `FAILED`.
   - **ENRIQUECIMIENTO** (Generate Posts, Fetch Images, Enrich Images, Generate Audio, Generate Video): fallo ⇒ registra `ERROR` en el step, **continúa**, estado final `PARTIAL` si hay fallos de enriquecimiento.
   - `GENERATE_POSTS` **no es crítico** (B18.1): fallo en generación de tweets no aborta publicación WordPress.
   - La criticidad vive en `ProcessingStepName.is_critical()` (`domain/entities/pipeline_job.py`), no en dict hardcodeado.
   - Los `try/except` con fallback en adaptadores de audio/vídeo se mantienen; el executor decide el estado final inspeccionando qué steps fallaron.
   - Estado `PARTIAL` añadido a `JobStatus` (`domain/entities/pipeline_job.py:19`). Contrato `PipelineResult` actualizado (§6).

---

## 6. CONTRATOS DE VOs

> Estos son los contratos mínimos. Si el código real difiere, **el código manda** — actualiza esta sección en el mismo PR. Verifica con `codegraph node <VO>`.

| VO | Campos esperados | Invariantes |
|---|---|---|
| `PipelineResult` | `job_id: str`, `status: JobStatus` (COMPLETED, PARTIAL, FAILED), `steps: list[PipelineStepResult]`, `error: Optional[str]`, `failed_steps: list[str]` | `status=PARTIAL` ⇒ `error` y `failed_steps` no vacíos (solo enriquecimiento). `status=FAILED` ⇒ `error` y `failed_steps` no vacíos (incluye crítico). `failed_steps` está en el contrato pero el frontend aún no lo consume. |
| `PipelineStepResult` | `name: ProcessingStepName`, `status: ProcessingStepStatus`, `error: Optional[str]`, `critical: bool` | `status=ERROR` ⇒ `error` no nulo. `critical=true` ⇒ paso crítico (aborta si falla). |
| `SocialPost` | `text: str`, `platform: SocialPlatform`, `title_es: Optional[str]` | `len(text) <= 280` para X/Bluesky |
| `PublishResult` | `platform: str`, `success: bool`, `url: Optional[str]`, `error: Optional[str]` | `success=False` ⇒ `error` no nulo |
| `PipelineContext` | `job_id`, `provider`, `article`, `post`, `images`, `audio_path`, `video_path` | — |

---

## 7. CONTRATOS Y DEPENDENCIAS EXTERNAS

### 7.1 AI Providers

> ⚠️ Default real de `AI_PROVIDER` es **`local`**, no `gemini`.

| Provider | Clave `.env` | Adaptador | Estado |
|----------|--------------|-----------|--------|
| `local` | (GPU opcional) | `local_adapter.py` | **DEFAULT REAL** (`settings.py:85`, `ai_factory.py:16`) |
| `gemini` | `GEMINI_API_KEY` | `gemini_adapter.py` | Soportado |
| `openrouter` | `OPENROUTER_API_KEY` | `openrouter_adapter.py` | Soportado |
| `groq` | `GROQ_API_KEY` | `groq_adapter.py` | ⚠️ **BUG (B5):** está en `AI_ADAPTER_MAP` (`settings.py:86`) pero **NO** en `SUPPORTED_AI_PROVIDERS` (`settings.py:93,105-107`) |
| `mock` | (no requiere) | `local_adapter.MockAdapter` | Mapeado en `settings.py:92` |

**Validación:** `GET /admin/providers` (⚠️ **no** `/news/providers`). El frontend usa la ruta correcta (`frontend/src/api/news.ts:30`). **No hardcodear proveedores.**

### 7.2 Publishers

> **X/Twitter: no soportado.** No existe adaptador de X/Twitter.

| Plataforma | Adaptador | Variables `.env` |
|-----------|-----------|-----------------|
| WordPress | `wordpress_publisher.py` / `wordpress_publisher_adapter.py` | `WP_USER`, `WP_PASSWORD`, `WP_HOSTING_API_BASE`, `WP_HOSTING_JWT_TOKEN` |
| Bluesky | `publishers/bluesky_publisher_adapter.py` + raíz `bluesky_publisher.py` | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` |
| Mastodon | `publishers/mastodon_publisher_adapter.py` + raíz `mastodon_publisher.py` | `MASTODON_ACCESS_TOKEN`, `MASTODON_INSTANCE_URL` |
| Facebook | `publishers/facebook_publisher_adapter.py` + raíz `facebook_publisher.py` | `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN` — cableado en facade (pipelines auto); CLI manual vía directa (flujo separado) |
| ~~X/Twitter~~ | ⚠️ **No implementado** | — (B16 cerrado) |

**X/Twitter: no soportado.** Las 5 credenciales (`X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`, `X_BEARER_TOKEN`) fueron eliminadas en B16 (2026-11-11) por ser huérfanas sin adaptador. Si se quiere soportar X en el futuro, implementar `x_publisher_adapter.py`, cablearlo en `composition_root.py` (y en el facade si se decide incluirlo), y añadir las credenciales de nuevo.

**Métodos del facade `SocialMediaPublisher` (`src/shared/adapters/publishers/social.py`):**
- `publish(post)` — single-post: publica un post concreto en plataformas habilitadas.
- `publish_all()` — batch: publica todos los pendientes desde DB en plataformas habilitadas. Usado por pipelines automáticos (`pipeline_runner.py`, `process_url_pipeline.py`). Fail-fast si una plataforma falla (`RuntimeError`).
- CLI manual (`news facebook`, `video facebook`) usa `run_facebook()` directo (flujo separado, no facade).

### 7.3 Image enrichment (orden de prioridad)

1. Unsplash (`unsplash_fetcher.py`)
2. Google Images (`google_images_fetcher.py`)
3. Wikimedia (`wikimedia_fetcher.py`)
4. Extracción del source (`og:image`, `twitter:image` vía `jina_extractor.py`)
5. Fallback: logo NBES por defecto

### 7.4 FFmpeg API (microservicio)

| Endpoint | Propósito | Cliente |
|----------|-----------|---------|
| `POST /audio/post-process` | Post-procesado TTS (normalización, breathing, plosives, compresión) | `audio_post_processor.py` |
| `POST /audio/apply-atempo` | Ajuste de tempo sin cambio de pitch | `coqui_tts_adapter.py` |
| `POST /audio/concatenate` | Concatenación lossless de audios | `tts_from_article.py` |

> ✅ **B17 CERRADO (2026-11-10, commit `faff1d6`):** `FFMPEG_API_URL` se fija en `docker-compose.yml` → servicio `app` → `environment: FFMPEG_API_URL=http://ffmpeg-api:8080`. En Docker Compose, `environment:` tiene precedencia sobre `env_file:`, por lo que **gana siempre** sobre cualquier valor en `.env` o `.config/ai-keys.env`. El servicio `ffmpeg-api` (externo, red `ffmpeg-cuda_ffmpeg-network`) escucha en 8080 interno. Los 176 `Connection refused` a `:5001` eran por la doble definición en `.env` + `.config/ai-keys.env`; la solución versionada elimina la ambigüedad.
>
> Timeout 300s por operación.

### 7.5 Caching

- Contenido extraído (Jina): 24 horas, en `cache_manager.py`.
- Flag `force_extract`: bypass de caché en `ProcessUrlRequest`.

---

## 8. AGENTES DE IA, PROMPTS Y TÍTULO

### 8.1 Agentes

| Agente | Prompt | Uso |
|--------|--------|-----|
| `article_agent` | `article.md` | Artículo periodístico desde RSS (SEO, geopolítica) |
| `article_from_content_agent` | `article-from-transcript.md` | Artículo desde transcripción audio/video |
| `tweet_agent` | `post-tweet.md` | Post/tweet sintético para publicación directa |
| `tweet_geopolitics_agent` | `tweet-geopolitics.md` | Tweet de geopolítica estilo The Economist |

### 8.2 Traducción y título (2026-10-04)

- El pipeline principal **NO llama al traductor de Google** (`src/shared/adapters/translator.py`). El endpoint web de Google bloquea el IP del servidor ("too many requests" persistente, verificado 2026-10-04), así que `translate_text` solo se usa en el flujo manual `article_from_news.py` y en el fallback sin IA.
- El LLM lo traduce todo por cuenta (regla 1 de `article.md`) y **genera el título en español**: abre el artículo con un `<h1>` con la traducción fiel del título original. `article.py::_extract_title_es` lo extrae antes de que `_limpiar_html` lo quite, y `execute()` lo escribe de vuelta en el post vía `GeneratedPostsRepository.update_post(url, {"title_es": ...})` para que Facebook/WordPress lo usen.
- Cadena de prioridad del payload: **título del LLM > `title_es` del post > original**.

### 8.3 Cambio post-auditoría conocido (2026-10-05)

> ⚠️ Commit `fix(content): publicabilidad del tweet la declara el LLM via JSON`. La publicabilidad del tweet **ya no se decide por heurística local**; el LLM la declara en JSON estructurado. Al tocar tweets, verifica el contrato JSON real en el prompt y en el adapter (`codegraph node tweet_agent` o `rg "publicable|publicability" src/shared/adapters/ai/`).

### 8.4 Reglas de los prompts (no negociables)

1. **Idioma:** 100% español. Prohibido inglés.
2. **Formato de salida:** solo HTML puro. El artículo **abre con un único `<h1>` con el TÍTULO EN ESPAÑOL** (traducción fiel del título original) y el resto usa `<h2>`, `<p>`, `<strong>`. Prohibido markdown.
3. **Prohibiciones globales:**
   - Primera persona ("creo", "nosotros", "yo").
   - Juicios de valor ("lamentablemente", "preocupante").
   - Abreviaturas con puntos (E.E.U.U., Sr., Dr.) — por TTS.
   - "..." al final del tweet/post.
   - Etiquetas estructurales en output ("Hecho:", "Contexto:").
   - Hashtags al final del texto (siempre intercalados).
4. **Estructura artículo:** 12-18 párrafos, 4-6 secciones `<h2>`, mínimo 800 palabras.
5. **Estructura tweet/post:** máximo 280 caracteres, 4-7 hashtags intercalados.
6. **SEO:** primer párrafo incluye la keyword principal; 3-5 repeticiones naturales.
7. **Legibilidad (Yoast):** 30% oraciones con palabras de transición, máx. 20% de oraciones >20 palabras, máx. 150 palabras por párrafo, máx. 10% voz pasiva.
8. **Fidelidad:** no inventar datos, fechas, cifras ni nombres. Si falta info, usa "recientemente" o "en las últimas semanas".

---

## 9. FLUJOS CRÍTICOS

### 9.1 "Procesar URL Concreta" (ProcessUrl)

**Endpoint:** `POST /news/process_url` · **Router:** `src/news/entrypoints/api/news_router.py:71`
**Coordinator:** `ProcessUrlJobCoordinator` (`process_url_executor.py`)
**Async wrapper:** `execute_pipeline_async` (`pipeline_executor.py`)

Flujo: validar URL y provider → crear job en `JobRepositoryPort` → **thread daemon SIN lock** (`process_url_executor.py:64`) ⚠️ race condition → extraer contenido (Jina o caché, respetando `force_extract`) → generar artículo IA → generar tweet/post → fetch imágenes → enriquecer → audio TTS → video → publicar WordPress → publicar social.

**Polling:** `GET /news/process_url/status/{job_id}` → `job_repository.get(job_id)`

> **Matiz:** la race por falta de lock aplica **solo** a `/process_url`. `pipeline_executor.py:28,50` **sí tiene** `_execution_lock`.

### 9.2 Pipeline Completo (RSS → Publish)

**Endpoint:** `POST /news/pipeline` · **Router:** `news_router.py:356` (`news_full_pipeline`)
**Implementación:** `execute_pipeline_async` en `pipeline_executor.py` — **no usa DI**, instancia `MongoMetricsRepository` y llama `get_database()` desde `application/` (`pipeline_executor.py:341-343,368-370`)
**CLI equivalente:** `main_pipeline()` en `pipeline_log_handler.py`
**Duración estimada:** 6-17 minutos (depende de Coqui TTS local).

### 9.3 Audio / Video pipelines

- `POST /audio/pipeline` → `audio_router.py` → URL de audio → descargar → transcribir → generar artículo → (opcional) publicar.
- `POST /video/pipeline` → `video_router.py` → URL de video → descargar → extraer audio → transcribir → generar artículo → (opcional) publicar.

---

## 10. DEPENDENCIES Y COMPOSITION ROOT

### 10.1 `dependencies.py` (API) — proveedores `Depends()`

`get_content_extractor` (Jina) · `get_article_repo` · `get_verified_news_repo` (Mongo) · `get_article_usecase` · `get_content_usecase` · `get_fetch_rss_usecase` · `get_full_verify_usecase` · `get_soft_verify_usecase` · `get_generated_posts_repo` · `get_process_url_job_coordinator` · `get_process_url_job_repository` (`InMemoryJobRepository` en `pipeline_job.py` — capa application correcta)

⚠️ **B4 resuelto:** las funciones `get_image_fetcher_usecase`, `get_image_enricher_usecase`, `get_publishers_usecase` y `ProcessUrlCompleteUseCase` ya no existen en el código (eliminadas en refactors previos).

### 10.2 `composition_root.py` (Shared)

- Audio: `create_audio_converter()`, `create_audio_post_processor()`, `create_tts_adapter()`, `create_audio_fetcher()`, `create_audio_transcriber()`
- Video: `create_video_generator()`, `create_video_fetcher()`, `create_video_transcriber()`
- AI: `create_ai_adapter(provider)`
- Publishing: `run_wordpress()`, `run_bluesky()`, `run_facebook()`, `run_mastodon()`, `run_image_unsplash()`, `run_image_google()`, `run_image_enricher()`

---

## 11. ERROR HANDLING, API Y SEGURIDAD

### 11.1 Estructura de error estándar

```json
{
  "status": "error",
  "message": "Mensaje amigable para el usuario",
  "error_code": "CONTENT_EXTRACTION_FAILED",
  "details": "Contexto adicional para el usuario",
  "context": { "...": "Solo en logs, NUNCA al cliente" }
}
```

### 11.2 Códigos de error

`INVALID_URL` · `CONTENT_EXTRACTION_FAILED` · `CONTENT_TOO_SHORT` (<100 chars) · `ARTICLE_GENERATION_FAILED` · `TWEET_GENERATION_FAILED` · `TTS_GENERATION_FAILED` · `VIDEO_GENERATION_FAILED` · `DATABASE_ERROR` · `SERVICE_UNAVAILABLE` · `INVALID_REQUEST` (incluye provider no soportado) · `PIPELINE_ERROR`

Registro: `from src.news.entrypoints.api.error_handlers import register_error_handlers; register_error_handlers(app)` en `server.py:32`.

### 11.3 Autenticación por API key (activa)

Middleware `require_api_key` (`server.py:54`) con `_PUBLIC_PATHS = {"/health"}` (`server.py:57-63`). **Solo `/health` es público.** Todos los `curl` necesitan `X-API-Key`.

<!-- CAMBIO 2026-11-10 -->
> **Ruido conocido (no es un fallo de esta app):** los `401 Unauthorized` en `/api/v1/market/price/*` y `/api/v1/market/candles/latest/*` son tráfico del contenedor `trading-fastapi` mal dirigido al puerto 8000 del host. Ignorar en análisis de logs. Si aparecen en los logs de `news_bot_hex`, no requieren acción.

### 11.4 Contrato con el frontend

> Si tocas el backend, **no rompas estos contratos**. Verifica la forma real en `frontend/src/api/news.ts` y en los routers antes de asumirla.

| Función (`api/news.ts`) | Endpoint | Método | Respuesta esperada |
|---------|----------|--------|--------------------|
| `processUrl()` | `/news/process_url` | POST | `{ data: { job_id } }` |
| `getProcessUrlStatus()` | `/news/process_url/status/{job_id}` | GET | `{ data: { status, progress, steps } }` |
| `getSupportedProviders()` | ⚠️ `/admin/providers` | GET | `{ data: { providers } }` |
| `runPipeline()` | `/news/pipeline` | POST | `{ data: { job_id } }` |
| `getPipelineStatus()` | `/news/pipeline/status/{job_id}` | GET | `{ data: { status, progress, steps } }` |

**Estados de job (`status`):** `pending` | `running` | `completed` | `partial` | `failed`.
- `completed`: todos los pasos OK.
- `partial`: ≥1 paso de enriquecimiento falló (audio/video/imágenes); publicación OK.
- `failed`: ≥1 paso crítico falló (RSS, verificación, artículos, WordPress, social).

**Feature "Forzar extracción con Jina":** checkbox en `NewsTab.tsx` → envía `force_extract: true` → `NewsToNewsUseCase` respeta el flag y omite caché.

### 11.5 Comandos de verificación

> ⚠️ **Todos requieren `X-API-Key`** salvo `/health`.

```bash
# Único endpoint público
curl http://localhost:8000/health | jq .database

# Requiere API key
curl -H "X-API-Key: $APP_API_KEY" http://localhost:8000/admin/providers | jq .data.providers

JOB_ID=$(curl -s -X POST -H "X-API-Key: $APP_API_KEY" \
  http://localhost:8000/news/pipeline | jq -r '.data.job_id')

watch -n 2 "curl -s -H 'X-API-Key: $APP_API_KEY' \
  http://localhost:8000/news/pipeline/status/$JOB_ID | jq '.data | {status, progress, steps}'"

systemctl --user status news-bot-pipeline.timer
```

---

## 12. CONFIGURACIÓN Y VARIABLES DE ENTORNO

> ⚠️ Verifica contra `config/settings.py` real antes de asumir ningún default.

| Variable | Req. | Default (HEAD) | Descripción |
|----------|------|---------|-------------|
| `MONGO_DB_NAME` | ✅ | `news_bot` | **Debe ser `appdb`** |
| `MONGO_URI` | ✅ | — | URI de MongoDB |
| `AI_PROVIDER` | ✅ | ⚠️ **`local`** | `local`, `gemini`, `openrouter`, `groq`, `mock` |
| `GEMINI_API_KEY` | Cond. | — | Provider `gemini` |
| `OPENROUTER_API_KEY` | Cond. | — | Provider `openrouter` |
| `GROQ_API_KEY` | Cond. | — | ⚠️ No llega a `SUPPORTED_AI_PROVIDERS` (B5) |
| `FFMPEG_API_URL` | ✅ | `http://ffmpeg-api:8080` | **Fijado en `docker-compose.yml` `environment:`** (gana sobre `.env` y `.config/ai-keys.env`). Ver B17 cerrado (`faff1d6`). |
| `APP_API_KEY` | ✅ | — | API key — **obligatoria para todo excepto `/health`** |
| `WP_*` | Cond. | — | WordPress |
| `BLUESKY_*`, `FACEBOOK_*`, `MASTODON_*` | Cond. | — | Redes sociales |
| `X_API_*` | — | — | No soportado; 5 credenciales eliminadas (B16, 2026-11-11)

---

## ANEXO A — DISCREPANCIAS RESUELTAS

| ID | Discrepancia | Resolución | Commit |
|----|--------------|------------|--------|
| B17 | `FFMPEG_API_URL` doble definición: `.env` (`http://ffmpeg-api-prod:8080`) + `.config/ai-keys.env` (`http://ffmpeg-api:5001/optimize`). La segunda gana por orden de carga en `env_file:`, causando 176 `Connection refused` a `:5001`. | Añadido `environment: FFMPEG_API_URL=http://ffmpeg-api:8080` al servicio `app` en `docker-compose.yml`. En Docker Compose, `environment:` tiene precedencia sobre `env_file:`. | `faff1d6` |
| B18.1 | VOs de pipeline (`JobStatus`, `ProcessingStepName`, `ProcessingStepStatus`, `PipelineStepResult`, `PipelineResult`) vivían en `application/usecases/pipeline_job.py` (violación hexagonal). `STEP_CRITICALITY` hardcodeado en executor con `GENERATE_POSTS: True` (incorrecto). `JobStatus` duplicado en `domain/entities/job.py` (sin PARTIAL). | Movidos VOs a `domain/entities/pipeline_job.py` (nuevo). `JobStatus` unificado con PARTIAL. `STEP_CRITICALITY` → `ProcessingStepName.is_critical()` en domain. `GENERATE_POSTS` pasa a enriquecimiento. `pipeline_step.py` importa enums de `pipeline_job.py`. | `08e7673` |
| B12 | `self.store = store or {}` en `InMemoryJobRepository` descartaba un dict vacío (falsy) y dejaba `_jobs_store` huérfano. | Cambiado a `store if store is not None else {}`. Test de regresión añadido. | `a70ca24` |
| B4 | Funciones sin consumidor en `dependencies.py` (`get_image_fetcher_usecase`, `get_image_enricher_usecase`, `get_publishers_usecase`) y `ProcessUrlCompleteUseCase`. | Verificación: ya no existen en el código (eliminadas en refactors previos). Nota en AGENTS.md actualizada. | `docs` (sin cambios de código) |
| B14 | Patrón "SKIPPED + raise" abortaba todo el pipeline en `pipeline_executor.py`. Reabierto en B18 (verificación de octubre insuficiente). Con la doctrina B18 (fallo en crítico ⇒ FAILED/aborta; fallo en enriquecimiento ⇒ PARTIAL/continúa), el patrón ya no existe: paso fallido se registra como ERROR y el executor decide el estado final por criticidad. Comportamiento actual correcto por diseño. | `docs` (sin cambios de código) |
| B15 | `posts[-1]` asume orden mono-hilo. Estaba en `process_url_complete.py` (código muerto), eliminado en B4. `rg posts[-1] src/` vacío; `ProcessUrlCompleteUseCase` solo en `tests/test_dead_code_removed.py`. Ya no existe. | `docs` (sin cambios de código) |

---

## ANEXO B — COMANDOS DE RE-VERIFICACIÓN (hallazgos caducables)

| Hallazgo | Comando de re-verificación | Frecuencia |
|----------|---------------------------|------------|
| **B3** | `get_database()` en `application/` — **7 ficheros, 12 llamadas** | 🔴 | `pipeline_executor.py` (4), `news_to_news.py` (1), `process_url_pipeline.py` (1), `article.py` (1), `content.py` (1), `__init__.py` (1), `news_to_news` (función en `__init__`) | **CERRADO** (2026-11-11: commits B3.1 `d6d8a4d`, B3.2 `fe5d44e`, B3.3a `fe5d44e`, B3.3b `94984dc`; `rg get_database src/*/application/ src/*/domain/` vacío) |
| B17 (puerto ffmpeg-api) | `docker compose exec app env | grep FFMPEG_API_URL` → debe salir `http://ffmpeg-api:8080` | Tras cualquier cambio en compose/env |
| B18 (PARTIAL enriquecimiento) | `docker logs news_bot_app | grep -c "Connection refused"` tras un run de pipeline → debe ser 0; `status` en job debe ser `PARTIAL` si falla audio/video; `FAILED` si falla publicación | Tras deploy o cambio en adaptadores de audio/vídeo o executor |
| B18.1 (VOs en domain, criticidad) | `grep -rn "class JobStatus" src/` → 1 línea en `domain/entities/pipeline_job.py`; `grep -n "is_critical" src/news/domain/entities/pipeline_job.py` → método presente; `pytest tests/test_pipeline_status_partial.py tests/test_pipeline_fail_fast.py -xvs` → GREEN | Tras cambios en domain entities o pipeline executor |
| B19 (tests bloqueados por .env con paths de Docker) | `.venv/bin/python -m pytest tests/test_settings.py tests/test_pipeline_status_partial.py -q` → 8+ passed; `.env` no debe contener `BASE_DIR=/app`, `DATA_DIR=/app/data`, `CACHE_DIR=/app/data/cache`, `MODELS_DIR=/app/models`, `IMAGES_DIR=/app/data/images`, `LOG_DIR=/app/logs` | Tras cambios en .env o docker-compose.yml |
| B6 (guard tests imports inline) | `pytest tests/test_architecture.py -q` → 288 passed, 10 failed (solo `test_adapter_implements_port` preexistente); 158 imports allowlisteados con `# TODO B20` en 22 ficheros | Tras cambios en tests/test_architecture.py o imports en application/ + domain/ |
| **B6b** (allowlist frágil por líneas) | `ALLOWED_IMPORTS` en `tests/test_architecture.py` clave `(fichero, módulo)` (robusta a desplazamiento); línea sigue en mensajes de error | Tras cambios en `tests/test_architecture.py` | **CERRADO** (2026-11-11: allowlist migrada a `dict[str,set[str]]`, comparaciones por módulo. `pytest tests/test_architecture.py -q` → 298 passed. Verificado: insertar línea en blanco en fichero allowlisteado no rompe; añadir import inline nuevo sí falla. Suite: 27 failed, 1101 passed, 41 skipped, 11 errors = baseline post-B16) |
| B21 (deuda PipelineRunner.run()) | `PipelineRunner.run()` mantiene 7 pasos como lambdas dentro de `run()` (RSS, Verify, Posts, Articles, Fetch Images, Enrich Images, WordPress); A3 de B2 pedía métodos privados (`_run_rss_fetch`, etc.). Solo `_run_audio`, `_run_video`, `_run_social` se extrajeron como funciones anidadas. Refactor A3 aplicado a medias, no un bug. | `pipeline_runner.py`: `run()` con 7 lambdas + 3 funciones anidadas; commits B2 `93cc5fb` |
| **B13** (doble publicación Facebook / facade no unificado) | `grep -n "run_facebook\|run_bluesky\|run_mastodon" src/news/application/usecases/pipeline_runner.py src/news/application/usecases/process_url_pipeline.py` → vacío; `pytest tests/test_b13_social_single_publish.py -q` → 3 passed; CLIs `news facebook`/`video facebook` mantienen vía directa manual | Tras cambios en pipelines/facade social | **CERRADO** (2026-11-11: `14e5d13` cableó Facebook en facade; `e2b18d7`,`a1df729`,`5b06aee`,`ee08473` migraron pipelines auto a `SocialMediaPublisher.publish_all()` batch; `4852e41` eliminó service locator con `create_social_publisher()` en `composition_root.py` e inyección obligatoria + wiring; `publish(post)` single-post sigue; CLI manual separado. Guards: `pytest tests/test_architecture.py -q` → 298 passed. Suite: 27 failed, 1101 passed, 41 skipped, 11 errors (mejor que pre-B13: 34 failed, 1091 passed, 11 errors). 6 fallos en `tests/src/test_process_url_endpoint.py` (NewsToNewsUseCase/process_news_url firma repos) preexistentes a B13-fix, verificados en `4852e41~1`). |
| **B11** (main() en application→cli) | `rg -n "^def main(" src/news/application/usecases/ src/audio/application/usecases/ src/video/application/usecases/` → vacío (main eliminado); `rg -n "def main_" src/*/entrypoints/cli/__init__.py` → `main_news_to_news` (188), `main_audio_to_news` (28), `main_video_to_news` (53) presentes | Tras cambios en entrypoints/cli/ | **CERRADO** (2026-11-11: commits `01e20b9`, `533d2ba`, `531a377`; `main()` movido a `entrypoints/cli/`, `_save_outputs` se queda en application/) |
| **B11b** (_save_outputs en application/, audio/video) | `python3` check: `AudioToNewsUseCase`/`VideoToNewsUseCase` sin `debug_output_repo` → 0; `PYTHONPATH=. pytest tests/test_json_debug_output_repository.py tests/src/test_audio_adapters.py tests/src/test_video_pipeline.py tests/src/test_audio_pipeline.py tests/src/test_video_pipeline_integration.py -q` → 64 passed; `audio_to_news.py`/`video_to_news.py` sin IO directa `json.dump`/`open` a `generated_*` ni `from config.settings import Settings` en `_save_outputs` (persistencia vía `DebugOutputRepository`→`JsonDebugOutputRepository`) | Tras cambios en application/usecases audio/video o wiring debug output | **CERRADO** (2026-11-11: `60cdacc` B11b 1/2 puerto+adaptador+factory+test; `d598275` B11b 2/2 migración audio/video, wiring `:304`/`:318`, tests actualizados, `_generate_tweet` redundante eliminado en `audio_to_news._save_outputs`; `article_file` conservado. Nota: `news_to_news._save_outputs` **no aplica** B11b — ya persiste vía repos inyectados/B3 y escribe `.md`; mención previa en Anexo B era errónea). |
| **B22** | Tests desactualizados por firmas cambiadas en B3/B13/B11b (10 tests) | 🟡 | `tests/src/test_process_url_endpoint.py` (6), `tests/src/test_news_pipeline_integration.py` (4) | **CERRADO** (2026-11-12: commit 697cdea; firmas actualizadas con Mocks/repos; suite unitaria 0 failed) |
| **B23** | Fallos de entorno en suite de test: 28 por `num2words` ausente, 14 por Mongo inaccesible, 2 por fetchers con Mongo real | 🟡 | `tests/src/test_number_to_words.py`, `test_infrastructure_validation.py`, `test_mongo_integration.py`, `test_news_usecases_detailed.py` | **CERRADO** (2026-11-12: commit 21cc81e; `num2words==0.5.14` instalado; markers `integration` + `pytest.ini`; 79 deselected en unitaria) |
| **B23b** | CI sin separación unit/integration: `.github/workflows/ci.yml` corre `pytest tests/ -v` sin filtro; con Mongo ausente, los tests de integración fallan en CI | 🟡 | `.github/workflows/ci.yml` | **ABIERTO** — añadir job unitario (`-m "not integration"`) + job integración con Mongo service |
| **B16** (5 credenciales X/Twitter huérfanas) | `grep -rn "X_API_KEY\|X_API_SECRET\|X_ACCESS_TOKEN\|X_ACCESS_SECRET\|X_BEARER_TOKEN" config/ .env.example src/` → vacío fuera de docs/histórico; no hay adaptador X | Tras cambios en settings/env | **CERRADO** (2026-11-11: eliminadas de `settings.API_KEYS` y `.env.example`; X no soportado, documentado en §7.2) |
| **B16b** (`TWITTER_POST_LIMIT` + opción Twitter/X en UI) | `settings.py:91` (`"twitter": ...TWITTER_POST_LIMIT`), `frontend/src/features/news/NewsTab.tsx:30` | — | **ABIERTO** — decisión de producto: ¿ocultar de UI o mantener para futuro? |
| **B16c** (`ALLOWED_VIDEO_DOMAINS` incluye `twitter.com`) | `settings.py:246`, `.env.example:244` | — | **ABIERTO** — decisión de producto: ¿mantener transcripción de vídeos externos o eliminar? |
| **B24 / B20.3a.3** (pipeline_runner: `__import__` dinámicos a entrypoints/application) | `grep -n "__import__" src/news/application/usecases/pipeline_runner.py` → vacío; `grep -n "entrypoints" src/news/application/usecases/pipeline_runner.py` → vacío; `pytest tests/test_architecture.py -q` → 302 passed; suite unitaria 0 failed | **CERRADO** (2026-11-12; steps 3-4 import top-level `run_content`/`run_articles`; steps 1-2 usan `rss_fetch_runner`/`full_verify_runner` inyectados; `execute_pipeline_async` y wiring `news_router`/tests actualizados; sin dependencia application→entrypoints en runner) |

### Baseline de suite (2026-11-12)

> **Baseline suite unitaria (2026-11-12, tras B23+B22):**
> - `pytest tests/src/ -m "not integration" -q` → **0 failed, 627 passed, 25 skipped, 79 deselected** (~3.5 min).
> - `pytest tests/test_architecture.py -q` → **302 passed**.
> - `pytest tests/src/test_number_to_words.py -q` → **28 passed**.
> - Tests de integración (Mongo): `pytest -m integration` → requieren Mongo levantado; documentados como B23.
