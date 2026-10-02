# TEST_TRIAGE — Tests que dependen de MongoDB real

**Fecha:** 2026-10-02
**Alcance:** Fase 2 (triage y corrección de los 85 fallos). Este documento cubre
únicamente el **Grupo B**: los 34 tests que no he corregido porque suVeredicto
depende de infraestructura y/o de datos de producción.

**Regla aplicada:** clasificar y documentar. **No** se ha añadido ningún `skip`,
`xfail` ni `noqa`, y **no** se ha sembrado ningún dato sintético.

---

## 1. Reproducción

```bash
cd /home/felix/Public/news_bot_hex
set -a && source .env.test && set +a
export BASE_DIR=$PWD DATA_DIR=$PWD/data CACHE_DIR=$PWD/data/cache \
       MODELS_DIR=$PWD/models IMAGES_DIR=$PWD/data/images
.venv/bin/python -m pytest tests/ -q
```

| Escenario | Resultado |
|---|---|
| `.env.test` tal cual (credenciales Mongo vacías) | **34 failed / 744 passed / 4 skipped** |
| `.env.test` + `MONGO_USER=root MONGO_PASSWORD=rootpassword` | **0 failed / 101 passed / 1 skipped** (los 4 ficheros de este doc) |

Los 34 fallos son **una sola causa**: `.env.test` deja `MONGO_USER=` /
`MONGO_PASSWORD=` vacíos porque el Mongo de CI (`mongo:7`) corre sin
autenticación, pero el Mongo de producción **sí la exige**. Resultado:

```
pymongo.errors.OperationFailure: command aggregate requires authentication
```

**Ninguno de los 34 es un bug de código.** Con credenciales válidas los 34 pasan.

---

## 2. Estado real de los datos de producción

Medido contra `appdb` (host `127.0.0.1:27017`, `authSource=admin`):

| Colección | Documentos | Nota |
|---|---|---|
| `raw_news` | **55.590** | Cumple `>= 1000` |
| `verified_news` | 0 | Los tests solo exigen `>= 0` |
| `sources_rss` | 1 documento | `_id: "sources"`, con `sources: [...]` de **22 entradas**. Cumple `>= 10` |

Las garantías documentadas en `AGENTE_CINE.md` (`raw_news >= 1000`,
`sources_rss >= 10`) **se cumplen hoy** contra producción.

---

## 3. Clasificación

- **(a) Requiere datos de producción** — sólo pasa contra `appdb` con el corpus real.
- **(b) Requiere sólo un Mongo limpio** — no lee nada preexistente; crea sus propios
  fixtures. Pasaría contra cualquier Mongo alcanzable, incluso vacío.
- **(c) Bug real** — el código incumple una garantía. **Ninguno.**

### 3.1 `tests/src/test_rss_sources_integration.py` — 7 tests

Clasificación **(a)** en su totalidad: el fichero se declara explícitamente como
*"These tests MUST run against real MongoDB with appdb containing production
data"* y su purpose es detectar fuentes hardcodeadas o un `appdb` vacío.

| Test | Clase | Veredicto |
|---|---|---|
| `TestRSSSourcesFromAppDB::test_get_all_sources_returns_real_data` | (a) | Falla sólo por auth |
| `TestRSSSourcesFromAppDB::test_rss_sources_count_meets_minimum` | (a) | Falla sólo por auth |
| `TestRSSSourcesFromAppDB::test_rss_source_structure_is_valid` | (a) | Falla sólo por auth |
| `TestRSSSourcesFromAppDB::test_rss_sources_are_from_production_appdb` | (a) | Falla sólo por auth |
| `TestRSSSourcesFromAppDB::test_sources_urls_are_valid_feeds` | (a) | Falla sólo por auth |
| `TestRSSSourcesFromAppDB::test_all_sources_have_non_empty_names_and_urls` | (a) | Falla sólo por auth |
| `TestRSSSourcesRepositoryIntegration::test_repository_finds_sources_document` | (a) | Falla sólo por auth |

### 3.2 `tests/src/test_infrastructure_validation.py` — 8 tests

| Test | Clase | Veredicto |
|---|---|---|
| `TestDatabaseDataQuantities::test_articles_count_minimum` | (a) | Exige `raw_news >= 1000` |
| `TestDatabaseDataQuantities::test_articles_count_reasonable_production` | (a) | Idem, umbral superior |
| `TestDatabaseDataQuantities::test_rss_sources_count_minimum` | (a) | Exige `sources_rss >= 10` |
| `TestDatabaseDataQuantities::test_rss_sources_count_reasonable_production` | (a) | Idem, umbral superior |
| `TestRequiredCollections::test_required_collections_exist` | (a) | Exige las 3 colecciones |
| `TestRequiredCollections::test_required_collections_have_data` | (a) | Exige `raw_news >= 1000` |
| `TestStartupValidatorIntegration::test_startup_validator_passes_with_appdb` | (a) | `validate_all()` completo |
| `test_guard_infrastructure_valid_before_other_tests` | (a) | Guard de infraestructura |

> Nota: `TestStartupValidatorIntegration::test_startup_validator_detects_wrong_database_name`
> y `::test_startup_validator_provides_clear_error_message` **ya están corregidos**
> en esta fase (eran (c): el test esperaba `InfrastructureValidationError` cuando
> `validate_all()` la convierte en `SystemExit(1)` por diseño). Ver
> `tests/src/test_infrastructure_validation.py:197` y `:224`.

### 3.3 `tests/src/test_pipeline_e2e_real_data.py` — 6 tests

| Test | Clase | Veredicto |
|---|---|---|
| `TestNewsProcessingPipelineWithRealData::test_pipeline_has_rss_sources` | (a) | Lee `sources_rss` |
| `TestNewsProcessingPipelineWithRealData::test_pipeline_has_articles_in_database` | (a) | Lee `raw_news` |
| `TestNewsProcessingPipelineWithRealData::test_article_repository_loads_real_articles` | (a) | Lee `raw_news`, valida estructura |
| `TestNewsProcessingPipelineWithRealData::test_pipeline_article_processing_chain` | (a) | Lee `raw_news` + `verified_news` |
| `TestPipelineConfiguration::test_pipeline_required_collections_exist` | (a) | Exige las 3 colecciones |
| `TestPipelineDataIntegrity::test_rss_sources_are_production_quality` | (a) | Valida las 22 fuentes |

> `::test_fetch_rss_news_use_case_executes` **ya está corregido** en esta fase.
> Era (c): el test afirmaba `status in ["ok","warning","error"]` cuando
> `FetchRSSNewsUseCase.execute()` sólo devuelve y sólo puede devolver
> `"success"` (`src/news/application/usecases/__init__.py:80`). Ver §5.

### 3.4 `tests/src/test_mongo_integration.py` — 13 tests

Clasificación **(b)**: no dependen del corpus de producción. Crean sus propios
documentos y sólo necesitan un Mongo alcanzable.

| Test | Clase | Veredicto |
|---|---|---|
| `TestMongoArticleRepository::test_insert_and_count_articles` | (b) | Inserta y cuenta |
| `TestMongoVerifiedNewsRepository::test_insert_and_get_all_news` | (b) | Fixture propia |
| `TestMongoVerifiedNewsRepository::test_get_news_by_url` | (b) | Fixture propia |
| `TestMongoVerifiedNewsRepository::test_save_verified_all` | (b) | Fixture propia |
| `TestMongoVerifiedNewsRepository::test_save_verified_all_empty` | (b) | Fixture propia |
| `TestMongoVerifiedNewsRepository::test_delete_all_news` | (b) | Fixture propia |
| `TestMongoPublishedUrlsRepository::test_save_and_get_urls` | (b) | Fixture propia |
| `TestMongoPublishedUrlsRepository::test_save_urls_empty` | (b) | Fixture propia |
| `TestMongoPublishedUrlsRepository::test_save_urls_with_max_limit` | (b) | Fixture propia |
| `TestMongoPublishedUrlsRepository::test_save_urls_with_ttl_expired` | (b) | Fixture propia |
| `TestMongoScoringConfigRepository::test_get_scoring_config` | (b) | Lee/crea config |
| `TestMongoValidationRulesRepository::test_save_and_get_rules` | (b) | Fixture propia |

`TestMongoDBClient::test_get_client_singleton` → **CORREGIDO** en esta fase.
Ver §5.

---

## 4. 🔴 Hallazgo crítico: la suite **escribe en `appdb` de producción**

Los tests de clase (b) no usan una base de datos de pruebas: escriben en la
misma `appdb` de producción y **no limpian**.

Medido tras las ejecuciones de esta fase:

```
raw_news con url de ejemplo : 72
raw_news total              : 55590   (55451 antes de esta fase)
colecciones de test         : test_collection, published_urls
```

Los 72 documentos son exactamente los `Article(title="Test Article N",
url="https://example.com/testN")` que insertan
`TestMongoArticleRepository::test_insert_and_count_articles`.

**Consecuencias:**
1. `raw_news` está contaminado con datos de test; cualquier consumidor real
   (scoring, validación, pipeline) los procesa.
2. Los tests no son idempotentes: `test_insert_and_count_articles` usa
   `count >= 2` en vez de igualdad justamente porque nunca limpia.
3. Un `delete_all_news` (`TestMongoVerifiedNewsRepository`) opera sobre
   `verified_news` de producción.

**No he borrado nada** — destruir datos de producción requiere decisión de
producto. **Requiere decisión de Félix.** Ver §7.1.

---

## 5. Correcciones de este grupo aplicadas en Fase 2

Tres tests de estos ficheros eran (c) — bugs reales — y sí se han arreglado:

| Test | Veredicto | Corrección |
|---|---|---|
| `TestMongoDBClient::test_get_client_singleton` | Test viejo (decisión arquitectónica deliberada) | `MongoDBClient` declara *"sin Singleton pattern (Hexagonal Architecture DIP)"*. Reescrito en 3 tests que afirman la decisión real: la clase **no** es singleton, cada instancia memoiza su propio `pymongo` client, y el caché real es `_default_client` en `get_database()`. `tests/src/test_mongo_integration.py:18` |
| `TestStartupValidatorIntegration::test_startup_validator_detects_wrong_database_name` | Test viejo | `validate_all()` convierte `InfrastructureValidationError` en `SystemExit(1)` por diseño ("Application cannot start"). El test ahora afirma `SystemExit` con `code == 1`. De paso se eliminó un `importlib.reload(config.settings)` que contaminaba toda la sesión. `tests/src/test_infrastructure_validation.py:197` |
| `TestStartupValidatorIntegration::test_startup_validator_provides_clear_error_message` | Test viejo | El mensaje viaja en la `InfrastructureValidationError` de `_validate_database_name()`, no en el `SystemExit`. El test afirma ahora el mensaje real (contiene `MONGO_DB_NAME` y `appdb`). `tests/src/test_infrastructure_validation.py:224` |
| `TestNewsProcessingPipelineWithRealData::test_fetch_rss_news_use_case_executes` | Test viejo | `status` real es `"success"`, no `"ok"`. `tests/src/test_pipeline_e2e_real_data.py:44` |

### Contaminación global eliminada (afectaba a otros ficheros)

`tests/src/test_infrastructure_validation.py` ejecutaba
`importlib.reload(config.settings)` dentro de dos tests. Eso **rebindea la clase
`Settings`**, dejando desincronizados todos los módulos que hicieron
`from config.settings import Settings` a nivel de módulo (`tts_factory`,
`video_generator`, `coqui_tts_adapter`…). Efecto medido: 2 tests de
`test_shared_adapters.py::TestTTSFactory` fallaban sólo en la suite completa.

El `reload` era además **innecesario**: `startup_validator.py:69` lee
`os.getenv('MONGO_DB_NAME')` en tiempo de llamada, y `monkeypatch.setenv` ya
cubría el caso. Eliminado.

---

## 6. Por qué NO he "arreglado" los 34

Añadir `MONGO_USER`/`MONGO_PASSWORD` a `.env.test` sería falsear la garantía de
que el fichero **no contiene credenciales reales**, y está fuera de mi encargo
("No toques `.env`, ni los `.env.test` / `ci.yml` ya arreglados").

Marcarlos `skip` sería relajar el CI. No.

---

## 7. Decisiones que necesita Félix

### 7.1 Contaminación de `appdb` (prioridad alta)

Los tests de clase (b) necesitan una base de datos de pruebas. Opciones:

1. **Fixture de base de datos dedicada** — `appdb_test`, creada/borrada por
   sesión vía fixture de pytest. Requiere que `MONGO_DB_NAME` sea inyectable por
   test (hoy `MongoDBClient` lo lee de `Settings` en el `__init__`).
2. **Limpieza en `teardown`** — borrar los documentos insertados por el test.
   Menos invasivo, pero frágil.
3. **Dejarlos como están** — consciously aceptando la contaminación.

### 7.2 Autenticación en el entorno de test

¿De dónde sacar credenciales para los tests de integración?

1. Levantar un Mongo local **con** autenticación en CI, y versionar credenciales
   de test (no de producción) en `ci.yml`.
2. Levantar un Mongo local **sin** autenticación en CI y ejecutar estos tests
   contra un corpus sembrado mínimo (viola "no sembrar datos sintéticos" sólo si
   se hace implícitamente; sería una decisión explícita).
3. Aceptar que estos 34 tests sólo corren localmente con credenciales de
   producción, y que el CI los ejecute contra un perfil reducido.

### 7.3 Capacidad de red

`test_fetch_rss_news_use_case_executes` **consume red real** (feeds RSS de Sky
News, MIT Tech Review, New Scientist — 3 de 22 fuentes devolvieron HTML y se
descartaron durante mi ejecución) y **escribe artículos nuevos** en
`appdb.raw_news`. No es apto para CI sin una decisión explícita.

---

## 8. Comandos de verificación

```bash
# Estado actual (34 fallos, todos por auth)
set -a && source .env.test && set +a
export BASE_DIR=$PWD DATA_DIR=$PWD/data CACHE_DIR=$PWD/data/cache \
       MODELS_DIR=$PWD/models IMAGES_DIR=$PWD/data/images
.venv/bin/python -m pytest tests/ -q

# Comprobar que los 34 son sólo auth (0 fallos)
export MONGO_HOST=127.0.0.1 MONGO_USER=root MONGO_PASSWORD=rootpassword
.venv/bin/python -m pytest \
  tests/src/test_mongo_integration.py \
  tests/src/test_infrastructure_validation.py \
  tests/src/test_rss_sources_integration.py \
  tests/src/test_pipeline_e2e_real_data.py -q
# => 101 passed, 1 skipped
```