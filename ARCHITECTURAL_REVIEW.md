# Architectural Review: news_bot_hex — "Procesar URL Concreta" Feature

## Executive Summary

The `news_bot_hex` codebase aspires to Hexagonal Architecture (Ports & Adapters) and shows real effort: a `domain/ports/__init__.py` defines abstract repositories; `dependencies.py` is labelled as a Composition Root; entities are dataclasses in `domain/entities`. However, the **"Procesar URL Concreta" feature is the weakest part of the hex boundary** in the project. It is implemented as a stack of four overlapping use-cases (`process_url_complete`, `process_url_with_publishing`, `process_url_executor`, plus the legacy `news_to_news.process_news_url`) that all do approximately the same orchestration with different levels of dependency injection. Two of those files are **dead code** that no router or CLI invokes.

### Top-level architectural verdict

| Dimension | Rating | Notes |
|---|---|---|
| Domain purity | Good | Only one minor leak (`config.logging_config` import in `validation_rules.py`) |
| Port design (news context) | Acceptable | Repositories well-defined; **no ports for AI, TTS-from-domain, social publishing, image fetching, WordPress, video** at the use-case level |
| Composition Root centralisation | **Poor** | `dependencies.py` exists but is bypassed by every adapter via in-function `from ... import` + `get_database()` / `get_ai_adapter()` service-locator calls |
| SRP at use-case level | **Poor** | `ProcessUrlCompleteUseCase` performs orchestration, persistence, adapter instantiation, conditional logic, and side-effects in one method |
| OCP | **Poor** | Adding a new social network or pipeline step requires editing every `process_url_*` and `pipeline_executor` module |
| DIP | **Poor** in this feature | Use-cases depend on concrete adapters (`unsplash_fetcher.run`, `SocialMediaPublisher`, `get_video_generator`) |
| Duplication | **High** | Same 9-step orchestration is duplicated 3× across `process_url_complete.py`, `pipeline_executor.py` and `publishing_pipeline.py` |
| Dead code | **High** | `process_url_with_publishing.py`, `process_url_executor.execute_process_url_async`, several legacy module helpers |
| Error handling | Inconsistent | Broad `except Exception: pass`; in `pipeline_executor` "skipped" status is set and then `raise` immediately undoes that classification |

### Critical (must-fix) issues

1. **Three parallel implementations of the same pipeline.** `ProcessUrlCompleteUseCase.execute` (9 steps), `execute_pipeline_async` (10 steps in `pipeline_executor.py`), and the trio in `publishing_pipeline.py` all reimplement the publish/enrich/fetch flow. Any bug fix must be made in three places.
2. **Service-Locator anti-pattern at the heart of the feature.** `process_url_complete.py` performs **eight runtime `from ... import` calls inside `execute()`**, instantiating concrete adapters. This nullifies the DI work done in `dependencies.py`.
3. **Composition Root is not centralised.** `get_process_url_usecase()` returns a `ProcessUrlCompleteUseCase()` with **no constructor arguments** — the use-case then self-injects via `get_database()` and inline imports. The DI container has no leverage over it; tests cannot substitute collaborators.
4. **Domain leak via `mongo_db.get_database()` inside a use-case.** `ProcessUrlCompleteUseCase.__init__` reaches into the infrastructure layer; an application-layer class must never know that storage is MongoDB.
5. **God-method**: `execute_pipeline_async.run_pipeline` is ~200 lines, 10 try/except blocks, mixing thread setup, DB access, adapter calls, and progress reporting.

### Top priority actions (in order)

1. Delete `process_url_with_publishing.py` and the legacy wrapper `execute_process_url_async` (dead code).
2. Introduce ports: `ImageFetcherPort`, `ImageEnricherPort`, `WordPressPublisherPort`, `SocialPublisherPort`, plus a thin `PipelineStep` abstraction (Command/Chain-of-Responsibility) — collapses the three parallel pipelines into one.
3. Refactor `ProcessUrlCompleteUseCase` to receive all 7 collaborators via constructor; move adapter instantiation to `dependencies.py`.
4. Replace `_default_repo` module-level singleton in `pipeline_job.py` with an injected `JobRepositoryPort` provided exclusively by the composition root.
5. Split `pipeline_executor.execute_pipeline_async` into a `PipelineRunner` + ordered list of `PipelineStep` objects.

---

## 1. Code Smells

### 1.1 Long Method — Critical
**`process_url_complete.py:21-106` (`ProcessUrlCompleteUseCase.execute`)** — 85 LOC of mixed orchestration, persistence, conditional logic and 8 inline imports. Each "Step" is a comment, not a method.

**`pipeline_executor.py:18-228` (`execute_pipeline_async.run_pipeline`)** — ~200 LOC, 10 sequential try/except blocks. Classic Sequential Cohesion procedure masquerading as a use case.

**`news_to_news.py:187-261` (`NewsToNewsUseCase.process_url`)** — 75 LOC, 4 responsibilities (extract, generate article, tweet, TTS, video).

### 1.2 Large Files / Large Classes
- `news_router.py` (580 lines, 11 endpoints, duplicated error-handling boilerplate). High.
- `unsplash_fetcher.py` (788) and `wordpress_publisher.py` (550) — symptom of god-modules in adapters (out of scope for this review but relevant context).

### 1.3 Primitive Obsession — High
The pipeline pervasively passes `Dict[str, Any]` around:
- `process_url_usecase: Callable[[str], Dict[str, Any]]` (executor)
- `post_data = {"tweet": ..., "url": ..., "wp_url": ..., "image_url": ...}` (process_url_complete:88)
- Job tracking uses `Dict` everywhere (`pipeline_job.py` `get(...) -> Optional[Dict]`)

There is **no `PipelineResult`, no `SocialPost` VO, no `JobView`**, despite a perfectly good `domain/entities/` folder.

### 1.4 Feature Envy — High
`process_url_complete.py:84-94` reaches into `result["article_data"]["article"]["url"]` and `post["image_url"]` to assemble a `post_data` dict. The use-case is rummaging through the bowels of another module's data structure.

### 1.5 Data Clumps — Medium
The quartet `(tweet, url, wp_url, image_url, hashtags)` appears verbatim in `SocialMediaPublisher.publish` (twice, lines 57-60 and 69-72) and is reconstructed in `process_url_complete.py:88`. Should be a `SocialPost` dataclass.

### 1.6 Duplicate Switch / Parallel Inheritance — Medium
`SocialMediaPublisher.publish` repeats the same try/except/append block for Bluesky and Mastodon. `pipeline_executor.py` repeats it again for Bluesky/Facebook/Mastodon. `publishing_pipeline.PublishersUseCase.execute` repeats it a third time for WordPress/Bluesky/Mastodon/Facebook. Four parallel hand-rolled "publish loops".

### 1.7 Speculative Generality — Low
`ProcessUrlWithPublishingUseCase` (process_url_with_publishing.py) was clearly built as a generic orchestrator with callable injection — but **no caller uses it**. Built for a flexibility never exercised.

### 1.8 Magic Strings — Medium
- Mongo collection names hardcoded: `"generated_articles"`, `"generated_posts"` (process_url_complete.py:31-32, 51, 84).
- Step labels duplicated as raw strings in `pipeline_executor` (e.g. `"Generate Audio"`, `"ok"`, `"skipped"`) while `ProcessingStepName`/`ProcessingStepStatus` enums exist for the same purpose in `pipeline_job.py`. The enums are used in `process_url_executor.py` but **not** in `pipeline_executor.py` — inconsistent.

### 1.9 Inline Imports as a smell — Critical (project-wide pattern)
`process_url_complete.py` alone has 9 `from ... import` statements inside `execute()`. This is used to "avoid circular imports", which itself signals layering violations.

---

## 2. Dead Code

| File / symbol | Status | Evidence |
|---|---|---|
| `src/news/application/usecases/process_url_with_publishing.py` (entire module) | **Dead** | `grep -rn ProcessUrlWithPublishingUseCase` returns no references outside tests/docs; `dependencies.get_process_url_usecase` builds `ProcessUrlCompleteUseCase` instead. |
| `process_url_executor.execute_process_url_async` (legacy wrapper, lines 124-137) | **Dead** | Comment says "Legacy function wrapper for backwards compatibility" — no callers in `src/`. |
| `pipeline_job.create_job / get_job / update_job_status / add_step / update_job_log` module-level helpers | **Partially dead** | `pipeline_executor.py` still calls them, but the new path (`process_url_executor.py`) uses the `JobRepositoryPort`. Two parallel APIs to the same singleton. |
| `pipeline_job.cleanup_old_jobs` | **Dead** | No callers anywhere (no scheduler invokes it). |
| `news_to_news.main()` (CLI in an application use-case file, lines 285-353) | Misplaced | Used only via `python -m`; mixes entrypoint concerns into application layer. |
| `news_to_news._save_outputs` JSON-file persistence | **Dead/legacy** | The Mongo path through `ProcessUrlCompleteUseCase` ignores these JSON files; they remain as side-effects nobody reads. |

---

## 3. Duplicated Functionality

### 3.1 Three parallel "publish pipeline" implementations
| Concern | Location A | Location B | Location C |
|---|---|---|---|
| Fetch Unsplash + Google images | `process_url_complete.py:36-39` | `pipeline_executor.py:85-89` | `publishing_pipeline.ImageFetcherUseCase` |
| Enrich images | `process_url_complete.py:43-44` | `pipeline_executor.py:100-102` | `publishing_pipeline.ImageEnricherUseCase` |
| TTS articles | `process_url_complete.py:48-60` | `pipeline_executor.py:113-131` | `tts_from_article.run_tts_from_articles` (called directly) |
| Video generation | `process_url_complete.py:64-71` | `pipeline_executor.py:140-163` | also in `news_to_news.process_url` (245) |
| WordPress publish | `process_url_complete.py:75-77` | `pipeline_executor.py:173-175` | `publishing_pipeline.PublishersUseCase` |
| Social publish | `process_url_complete.py:81-94` (via `SocialMediaPublisher`) | `pipeline_executor.py:186-208` (direct `run_bluesky/run_facebook/run_mastodon`) | `publishing_pipeline.PublishersUseCase` (same direct calls) |

The same 6-step sequence is implemented in **three different styles** with three different failure semantics.

### 3.2 Duplicated job-tracking surface
`pipeline_job.py` exposes both a `JobRepositoryPort` + `InMemoryJobRepository` **and** module-level free functions (`create_job`, `update_job_status`, etc.) that wrap the same singleton `_default_repo`. New code (`process_url_executor`) uses the port; old code (`pipeline_executor`, `pipeline_log_handler`) uses the free functions. Two APIs, one state, easy desynchronisation.

### 3.3 Duplicated error-response boilerplate
In `news_router.py`, every endpoint has the same `except RepositoryError -> http_error(503, "DATABASE_ERROR", ...) / except Exception -> http_error(500, "PIPELINE_ERROR", ...)` block (lines 178-196, 233-251, 264-281, 297-315, 342-359, 376-385). Should be a FastAPI exception handler.

---

## 4. SOLID Violations

### 4.1 SRP — Critical
**`ProcessUrlCompleteUseCase`** owns:
1. DB connection acquisition (`__init__` line 19)
2. Pipeline orchestration
3. Direct MongoDB write semantics (insert_one of raw dicts, lines 31-32)
4. Adapter instantiation (8 inline imports)
5. Conditional execution and progress-style logging
6. Result assembly for the caller

**`InMemoryJobRepository`** also conflates:
- Job persistence
- Progress percentage calculation (`add_step` line 124-126 computes %)
- Timestamp lifecycle management
- Step deduplication

These should be separate domain services.

### 4.2 OCP — Critical
Adding a new pipeline step (e.g., Telegram) requires:
- Editing `pipeline_executor.py` (insert a new try/except block)
- Editing `process_url_complete.py` (insert another stage)
- Editing `SocialMediaPublisher.publish` to add another conditional
- Editing `publishing_pipeline.PublishersUseCase.execute`
The system is *closed for extension and open for modification*.

A polymorphic `PipelineStep` abstraction (each step = a class implementing `execute(context) -> context`) with an ordered registry would let new steps be added without modifying existing ones.

### 4.3 LSP — Low
No clear LSP violation found; the `JobRepositoryPort` -> `InMemoryJobRepository` substitution is clean. `ContentExtractor` -> `JinaContentExtractor` likewise. Note however the **`process_url_complete._process_url` passes `content_extractor=None`** (line 115) — the call signature of `process_news_url` accepts a port that can be `None`, indicating the port contract is not enforced (more LSP-adjacent than LSP proper).

### 4.4 ISP — Medium
`JobRepositoryPort` has 5 methods. Read consumers (status endpoint) need only `get`. Writers (`process_url_executor`) use the rest. Could split into `JobReader` + `JobWriter`.

`VerifiedNewsRepository` has 6 abstract methods (`get_all_news`, `get_news_by_url`, `get_verified_news`, `insert_news`, `delete_all_news`, `save_verified_all`). `SoftVerifyUseCase` likely needs ~2 of those. Fat interface.

### 4.5 DIP — Critical
Two layered violations:

a) **Application depending on infrastructure (concrete)**:
- `process_url_complete.py:9, 19` imports and calls `get_database()` (a Mongo singleton).
- `process_url_complete.py:36-94` imports concrete `unsplash_fetcher`, `google_images_fetcher`, `image_enricher`, `tts_from_article`, `video_generator`, `wordpress_publisher`, `SocialMediaPublisher`.
- `news_to_news.NewsToNewsUseCase._get_ai_model` calls the concrete factory `get_ai_adapter` rather than receiving an `AIModelPort`.

b) **Composition Root not enforced**: `dependencies.get_process_url_usecase` returns `ProcessUrlCompleteUseCase()` — no parameters — defeating the DI container.

---

## 5. Hexagonal Architecture Issues

### 5.1 Domain Layer Contamination — Low (but present)
`src/news/domain/services/validation_rules.py:12` imports `from config.logging_config import get_logger`. The domain depends on a framework-flavoured config module. Should inject a logger or use `logging.getLogger(__name__)` from stdlib only.

Otherwise `src/news/domain/` is clean (entities, ports, services) — credit where due.

### 5.2 Missing Ports — High
Ports exist only for **repositories**, content extraction, RSS, fake-news. The following collaborators are **invoked by application use-cases as concrete modules**, with no port between them:

| Capability | Concrete dependency | Missing port |
|---|---|---|
| Image fetching (Unsplash/Google) | `unsplash_fetcher.run`, `google_images_fetcher.run` | `ImageSourcePort` |
| Image enrichment | `image_enricher.run` | `ImageEnricherPort` |
| WordPress publishing | `wordpress_publisher.run` | `ArticlePublisherPort` |
| Social publishing | `SocialMediaPublisher`, `BlueskyPublisher`, etc. | `SocialPublisherPort` |
| Video generation | `get_video_generator()` (singleton) | exists (`VideoGeneratorPort`) but bypassed by `get_video_generator()` global accessor |
| AI model | `get_ai_adapter` (factory) | `AIModelPort` exists but `news_to_news` reaches the factory directly |
| TTS | `TTSFromArticleUseCase` (concrete) | `tts_port.py` exists, but `news_to_news.process_url:206-211` imports the use-case directly |

The presence of half the ports makes the omissions glaring.

### 5.3 Adapters Misplaced — Medium
`InMemoryJobRepository` (an adapter) lives in `application/usecases/pipeline_job.py`, mixed with the port itself and the global singleton. Hex layout would put the port in `domain/ports/` and the adapter in `infrastructure/adapters/`. The same file holds three different concerns: the port (abstraction), the adapter (impl), and a module-level singleton wrapping it — a textbook **service locator**.

### 5.4 Inbound/Outbound Port Boundaries Unclear — High
The "inbound port" for "Procesar URL Concreta" should be a single use-case interface, e.g. `ProcessUrlPort.execute(url)`. Instead the router talks to `ProcessUrlJobCoordinator` (an executor, not a use case), which calls a `Callable[[str], Dict]` (lambda from `dependencies.py`) that wraps `ProcessUrlCompleteUseCase.execute`. **Three layers of indirection**, all in the application layer.

### 5.5 Composition Root Not Centralised — Critical
`dependencies.py` claims to be the composition root but:
- `get_process_url_usecase()` returns a class with **zero injected dependencies**.
- `process_url_complete.py` then imports concrete adapters at runtime (8 of them).
- `pipeline_executor.execute_pipeline_async` is a free function that imports + instantiates everything inline (12 inline imports).
- `news_to_news.NewsToNewsUseCase._get_default_video_generator` calls `get_video_generator()` — another mini-locator.

A real composition root would wire all 7 collaborators in `dependencies.py` and the use-case would have a constructor like `__init__(self, content_processor, image_fetcher, image_enricher, tts_service, video_service, wp_publisher, social_publisher, articles_repo, posts_repo)`.

---

## 6. Other Anti-Patterns

### 6.1 Service Locator — Critical
- `pipeline_job._default_repo` (module-level global) accessed via `get_process_url_job_repository()`.
- `mongo_db.get_database()` (process-wide singleton).
- `video_generator.get_video_generator()` (singleton accessor).
- `ai_factory.get_ai_adapter(provider, config)` (locator with key).
All four short-circuit dependency injection.

### 6.2 Hidden Dependencies — High
`ProcessUrlCompleteUseCase()` constructor takes no args, yet at runtime depends on MongoDB, Unsplash API, Google Images, an image enricher, a TTS pipeline, a video generator, WordPress, Bluesky and Mastodon. Tests cannot enumerate these dependencies without reading the implementation.

### 6.3 Anemic Domain Model + Transaction Script — High
The domain has `Article` and `VerifiedArticle` dataclasses with only `to_dict()` (no behaviour). All workflow logic lives as procedural scripts in `usecases/*.py`. `ProcessUrlCompleteUseCase.execute` is a textbook **Transaction Script** (Fowler) — 80 lines of step-by-step procedural code.

### 6.4 God Module
`pipeline_executor.execute_pipeline_async.run_pipeline` is a 200-line god-function. `unsplash_fetcher.py` (788) and `wordpress_publisher.py` (550) are god-modules.

### 6.5 Improper Error Handling — High
- `pipeline_executor.py:131-135`: catches Exception, sets step to `"skipped"`, then `raise` — the `raise` will overwrite the skipped status downstream by going to the outer except which calls `update_job_status(FAILED)`. The `"skipped"` marker is meaningless.
- `pipeline_log_handler.emit` swallows all exceptions silently (`except Exception: pass`) — debugging logging failures becomes impossible.
- `news_to_news.process_url:220-245`: catches Exception, logs "no bloquea" and continues — but the upstream `ProcessUrlCompleteUseCase` will then `raise` on the same kind of issue. Inconsistent recovery semantics.
- `process_url_complete.py:104-106`: catches `Exception`, logs, re-raises — but leaves the database in a partial state (article inserted, video not generated, no rollback / Saga / Outbox).
- No retry on transient I/O failures despite `shared/utils/retry.py` existing.

### 6.6 Threading without back-pressure — Medium
`execute_async` and `execute_pipeline_async` spawn `daemon=True` threads with **no concurrency limit, no queue, no cancellation token**. Two clients hitting `/process_url` → two unbounded background pipelines hitting the same Mongo collections (`"generated_articles"`, `"generated_posts"`) concurrently. Race conditions guaranteed (`posts[-1]` in `process_url_complete.py:87` will pick whichever post happened to land last across threads).

### 6.7 Global Mutable State — High
`pipeline_job._jobs_store: Dict[str, Dict]` module-level dict, mutated by background threads with **no lock**. The "in-memory" caveat is acknowledged but the lack of `threading.Lock()` is a real concurrency bug.

### 6.8 Tight Coupling
- `process_url_complete.py:84-87`: assumes "the most recent post in Mongo belongs to the URL we just processed" (`posts[-1]`). Coupling to insertion order; breaks with any concurrent job.
- `SocialMediaPublisher.__init__` silently swallows init failures (`except Exception as e: logger.warning(...)`) and leaves the attribute `None`, hiding misconfiguration until first publish call.

---

## 7. File-by-file Findings

### 7.1 `src/news/application/usecases/process_url_complete.py`
- **Severity: Critical.**
- DIP violation: depends on 8 concrete adapters via inline imports.
- SRP violation: orchestration + persistence + DB access + adapter assembly.
- Hidden side-effect on global Mongo singleton (`get_database`).
- Race condition: `posts[-1]` selection assumes single-threaded execution.
- Magic strings for collection names.
- "Pure orchestrator - no dependencies to inject" docstring (line 18) is **factually wrong** — every step has a concrete dependency.

**Recommended fix**: replace with
```python
class ProcessUrlCompleteUseCase:
    def __init__(self, content_processor, image_fetcher, image_enricher,
                 tts_service, video_service, wp_publisher, social_publisher,
                 articles_repo, posts_repo): ...
    def execute(self, url): ...  # each step = one collaborator call
```
and have `dependencies.get_process_url_usecase()` wire it.

### 7.2 `src/news/entrypoints/api/dependencies.py`
- **Severity: High.**
- Repeats `from src.news.infrastructure.adapters import X; from src.news.domain.ports import X` inside every provider (lines 32-86); imports `X` for type annotation but never uses the variable — likely **unused import per function**.
- `get_process_url_usecase` is a thin factory returning a zero-arg constructor — the only function in the file that **doesn't** practice DI.
- `get_process_url_job_repository` returns the module-level `_default_repo` (service locator hand-off), not a freshly-scoped per-request adapter. For an in-memory store across requests this is fine, but the file calls itself the Composition Root while leaking a global.
- Mixes Spanish + English docstrings; minor style issue.

### 7.3 `src/news/application/usecases/process_url_executor.py`
- **Severity: Medium.**
- `ProcessUrlJobCoordinator` is well-designed (DI via constructor, port-based). One of the cleanest classes in the feature.
- Issues:
  - `_run_with_tracking` has nested try/except whose inner block already updates job to FAILED and re-raises; outer except in `run_process` will then check `self.job_repository.get(job_id)` (line 57) and update FAILED **again** — double-write, second message overwrites the more specific one.
  - Status `JobStatus.RUNNING` updated **before** `INITIALIZING` step is added (line 72 vs 77) — race window for clients that poll between the two.
  - Dead code: `execute_process_url_async` legacy wrapper (lines 124-137) imports `get_process_url_job_coordinator` lazily — circular-import-avoidance smell.

### 7.4 `src/news/application/usecases/pipeline_job.py`
- **Severity: High.**
- Mixes Port (`JobRepositoryPort`), Adapter (`InMemoryJobRepository`), Singleton (`_default_repo`) and procedural API (`create_job`, etc.) in one file.
- `update_status` silently no-ops if `job_id not in self.store` — should raise or log; silent failure hides bugs.
- `add_step` recomputes progress as completed/total — but `total` is the count of steps *added so far*, so progress is always 100% for the final completed step, and misleadingly high during execution.
- `cleanup_old_jobs` references the module-level `_jobs_store` directly (line 171) instead of going through the repository abstraction — leaks abstraction.
- No locking; thread-unsafe.

### 7.5 `src/news/entrypoints/api/news_router.py`
- **Severity: High.**
- 580 lines, 11 endpoints; many endpoints (timer, providers, status, config) are **infrastructure/admin** concerns inside `news_router`.
- Duplicated error mapping (sections 7 above) — should move to `@app.exception_handler`.
- `news_full_pipeline` (line 362) does **not** use DI — directly imports `create_job`, `execute_pipeline_async`. Inconsistent with `news_process_url` which does use DI. Two coexisting styles.
- `news_content` (line 318) instantiates `ContentUseCase` **manually** inside the endpoint (line 330) bypassing the existing `get_content_usecase` provider — another DI bypass.
- Uses `subprocess.run(["systemctl", ...])` inside the API layer — **infrastructure leak in an HTTP handler**, also blocking I/O in async-style FastAPI.

### 7.6 `src/shared/adapters/` (relevant ones)
- `mongo_db.get_database()` — **Service Locator**. Used by application layer.
- `publishers/social.py` — Conflates a facade with conditional construction; should be a polymorphic `SocialPublisherPort` with multiple adapters injected as a list.
- `bluesky_publisher.py` / `facebook_publisher.py` — each does its own `get_database()` inside (`bluesky_publisher.py:105-107, 120-122`; `facebook_publisher.py:51-67`); adapters reaching for their own infrastructure is acceptable, but the duplication of "load latest post from Mongo" logic across publishers is itself a port candidate (`PendingPostsRepository`).
- `video_generator.get_video_generator` — global singleton; consumers call it inline rather than receiving `VideoGeneratorPort`.
- `ai/ai_factory.get_ai_adapter` — locator-style factory; called from inside `news_to_news.NewsToNewsUseCase._get_ai_model` (application layer reaching infra factory).

### 7.7 Related: `news_to_news.py` and `pipeline_executor.py`
Already covered above. Both are central to the feature and exhibit the same DIP/SRP problems.

---

## 8. Severity Summary

| ID | Issue | Severity | Effort |
|---|---|---|---|
| C1 | Three parallel pipeline implementations (process_url_complete / pipeline_executor / publishing_pipeline) | Critical | L |
| C2 | `ProcessUrlCompleteUseCase` ignores DI and uses 8 inline imports | Critical | M |
| C3 | Composition Root not centralised; `get_process_url_usecase()` takes no args | Critical | M |
| C4 | Domain/application code calls `get_database()` (Mongo singleton) | Critical | M |
| C5 | `pipeline_executor.execute_pipeline_async` is a 200-line god function | Critical | L |
| H1 | Dead code: `process_url_with_publishing.py`, legacy `execute_process_url_async`, `cleanup_old_jobs` | High | S |
| H2 | Module-level mutable `_jobs_store`, no locking, thread-unsafe | High | S |
| H3 | Missing ports for Images / WP / Social / Enricher | High | L |
| H4 | Anemic domain (`Dict[str, Any]` everywhere), Primitive Obsession | High | M |
| H5 | `news_router.py` mixes timer/systemctl/admin endpoints with news endpoints; duplicated error boilerplate | High | M |
| H6 | Race condition: `posts[-1]` assumes single-threaded ordering | High | S |
| H7 | Improper error handling: `"skipped"` + immediate `raise`, swallowed exceptions in `pipeline_log_handler` | High | S |
| M1 | ISP: `JobRepositoryPort` and `VerifiedNewsRepository` are fat interfaces | Medium | S |
| M2 | Duplicated "publish to platform X with try/except" loop in 4 places | Medium | M |
| M3 | Magic strings for step names in `pipeline_executor.py` while enums exist | Medium | S |
| M4 | `news_to_news.py` mixes CLI (`main()`) into application use case | Medium | S |
| M5 | `SocialMediaPublisher.__init__` swallows init failures silently | Medium | S |
| L1 | Domain leak: `validation_rules.py` imports `config.logging_config` | Low | S |
| L2 | Spanish/English mixed naming and docstrings | Low | S |
| L3 | `news_to_news._save_outputs` writes JSON files nobody reads | Low | S |

---

## 9. Recommended Refactor Sequence

**Sprint 1 — Cleanup (low risk):**
1. Delete `process_url_with_publishing.py`.
2. Delete `execute_process_url_async` legacy wrapper and `cleanup_old_jobs` (or wire to a cron).
3. Move admin endpoints (`/timer/*`, `/providers`) out of `news_router.py` into `admin_router.py`.
4. Replace ad-hoc step strings in `pipeline_executor.py` with the `ProcessingStepName/Status` enums already defined.
5. Add a `threading.Lock` to `InMemoryJobRepository`.

**Sprint 2 — Ports & DI (medium risk):**
6. Define ports: `ImageSourcePort`, `ImageEnricherPort`, `ArticlePublisherPort`, `SocialPublisherPort`. Move existing fetchers/publishers behind them.
7. Refactor `ProcessUrlCompleteUseCase` constructor to receive all collaborators; move wiring to `dependencies.py`.
8. Introduce `PipelineStep` ABC and rewrite `execute_pipeline_async` as `PipelineRunner(steps=[...])`.
9. Move `InMemoryJobRepository` to `src/news/infrastructure/adapters/`; keep only port in `pipeline_job.py` (or `domain/ports/`).
10. Replace `mongo_db.get_database()` calls in application layer with injected repos.

**Sprint 3 — Domain hardening:**
11. Introduce `PipelineContext`, `SocialPost`, `PublishResult` value objects to kill Primitive Obsession.
12. Extract publish-loop into a polymorphic list of `SocialPublisher` adapters iterated by the use case.
13. Use a Saga or Outbox pattern for the multi-step pipeline so partial failures are tracked and resumable.
14. Centralise FastAPI error mapping via `@app.exception_handler(RepositoryError)` etc.; remove try/except boilerplate from routers.

---

## 10. Relevant absolute file paths

- /home/felix/Public/news_bot_hex/src/news/application/usecases/process_url_complete.py
- /home/felix/Public/news_bot_hex/src/news/application/usecases/process_url_executor.py
- /home/felix/Public/news_bot_hex/src/news/application/usecases/process_url_with_publishing.py  *(dead)*
- /home/felix/Public/news_bot_hex/src/news/application/usecases/pipeline_job.py
- /home/felix/Public/news_bot_hex/src/news/application/usecases/pipeline_executor.py
- /home/felix/Public/news_bot_hex/src/news/application/usecases/pipeline_log_handler.py
- /home/felix/Public/news_bot_hex/src/news/application/usecases/publishing_pipeline.py
- /home/felix/Public/news_bot_hex/src/news/application/usecases/news_to_news.py
- /home/felix/Public/news_bot_hex/src/news/entrypoints/api/news_router.py
- /home/felix/Public/news_bot_hex/src/news/entrypoints/api/dependencies.py
- /home/felix/Public/news_bot_hex/src/news/domain/ports/__init__.py
- /home/felix/Public/news_bot_hex/src/news/domain/services/validation_rules.py  *(minor leak)*
- /home/felix/Public/news_bot_hex/src/shared/adapters/mongo_db.py  *(service-locator source)*
- /home/felix/Public/news_bot_hex/src/shared/adapters/publishers/social.py
- /home/felix/Public/news_bot_hex/src/shared/adapters/video_generator.py  *(get_video_generator singleton)*
- /home/felix/Public/news_bot_hex/src/shared/adapters/ai/ai_factory.py  *(get_ai_adapter locator)*
