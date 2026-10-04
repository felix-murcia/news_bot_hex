# Troubleshooting: Pipeline No Publica

## Estado Actual del Pipeline
El pipeline implementa **10 pasos** en `pipeline_executor.py` (ver `docs/PIPELINE_ASYNC_API.md`):
1. RSS fetch
2. Full verification
3. Generate posts/tweets
4. Generate professional articles (el LLM traduce el contenido y genera el título en español como `<h1>`; `article.py` lo extrae y lo escribe como `title_es` en el post)
5. Fetch images (Unsplash + Google)
6. Image enrichment
7. **Generate audio (TTS)** — Coqui XTTS v2 por HTTP
8. **Generate videos from audio** — usa la imagen enriquecida del artículo (descargada al pool `/tmp/images`); si no hay imagen válida ni en el pool, el paso aborta
9. Publish to WordPress
10. Publish Social (Facebook + Bluesky + Mastodon)

> **Doctrina fail-fast (2026-10-02):** cualquier paso fallido se registra como `ERROR`
> (métrica `FAILED`) y **aborta el pipeline**. Nunca se marca `SKIPPED` un paso que se intentó.

## Diagnóstico: Por Qué No Publica

### Paso 1: Verificar que hay noticias verificadas
```bash
# En el contenedor Docker, conectarse a MongoDB:
docker exec -it news_bot_app mongosh "mongodb://mongodb:27017"   # el host de Mongo es `mongodb` en la red docker

# Dentro de mongosh:
use appdb
db.verified_news.countDocuments()
```

**Si retorna 0**: No hay noticias verificadas. El problema está en el paso 2 (Full Verification).

### Paso 2: Verificar posts generados
```bash
# En mongosh:
db.generated_posts.countDocuments()
db.generated_posts.findOne()  # Ver estructura
```

**Si retorna 0**: No hay posts. El problema está en el paso 3 (Generate posts/tweets).

### Paso 3: Verificar artículos generados
```bash
# En mongosh:
db.generated_articles.countDocuments()
db.generated_articles.findOne()  # Ver estructura
```

**Si retorna 0**: No hay artículos. El problema está en el paso 4 (Generate articles).

### Paso 4: Verificar logs del contenedor
```bash
docker logs news_bot_app --tail 200
```

Busca mensajes como:
- `[CONTENT] No hay noticias verificadas` → Problema en paso 2
- `[ARTICLE] No hay posts para procesar` → Posts no se guardaron
- `[WORDPRESS] No hay artículos para publicar` → Artículos no se guardaron

## Flujo de Datos Entre Pasos

### Flujo esperado:
```
[RSS FETCH]
    ↓
[raw_news] collection
    ↓
[FULL VERIFY] (lee de raw_news, escribe a verified_news)
    ↓
[verified_news] collection
    ↓
[GENERATE POSTS] (lee de verified_news, escribe a generated_posts)
    ↓
[generated_posts] collection
    ↓
[GENERATE ARTICLES] (lee de generated_posts, escribe a generated_articles)
    ↓
[generated_articles] collection
    ↓
[PUBLISHERS] (leen de generated_articles y generated_posts)
    ↓
[WordPress, Facebook, Bluesky, Mastodon]
```

## Problemas Comunes

### 1. "No hay noticias verificadas"
**Causa**: El paso Full Verification no está guardando en `verified_news`

**Solución**: Verificar:
```bash
# ¿Hay artículos raw?
db.raw_news.countDocuments()

# ¿El verify está fallando?
docker logs news_bot_app | grep "VERIFIER\|VERIFY\|Error"
```

### 2. "No hay posts para procesar"
**Causa**: `run_content()` no está guardando en `generated_posts`

**Solución**: Verificar:
```bash
# Ejecutar solo content generation:
curl -X POST http://localhost:8000/content

# Ver logs:
docker logs news_bot_app | grep "CONTENT"
```

### 3. "No hay artículos para publicar"
**Causa**: `run_article()` no está generando/guardando artículos

**Solución**: Verificar:
```bash
# Ejecutar solo article generation:
curl -X POST http://localhost:8000/article

# Ver logs:
docker logs news_bot_app | grep "ARTICLE"
```

### 4. Publishers no publican
**Causa**: Faltan credenciales en .env

**Solución**: Verificar en docker-compose.yml:
```yaml
environment:
  - WP_HOSTING_JWT_TOKEN=<token>
  - BLUESKY_HANDLE=<handle>
  - BLUESKY_APP_PASSWORD=<password>
  - FACEBOOK_PAGE_ID=<id>
  - FACEBOOK_PAGE_ACCESS_TOKEN=<token>
  - MASTODON_INSTANCE_URL=<url>
  - MASTODON_ACCESS_TOKEN=<token>
```

### 5. El título del artículo/wp sale en inglés
**Causa:** el LLM no emitió el `<h1>` con la traducción, o el post guardado es de antes del cambio.

**Solución:**
```bash
# Ver si el LLM devolvió el título (log de "Generate Articles"):
docker logs news_bot_app 2>&1 | grep "Título en español del LLM"
```
- Si la línea NO aparece: el modelo no emitió el `<h1>` → refinar `src/shared/adapters/ai/prompts/article.md` (regla 4).
- Si aparece pero el post sigue sin `title_es`: verificar que el paso Generate Articles completó (`update_post` sobre `generated_posts`).

**Nota:** el pipeline principal **no llama al traductor de Google** desde 2026-10-04; `translate_text` solo se usa en el flujo manual `article_from_news.py` (news_man) y en el fallback sin IA.

### 6. `[TRANSLATOR] Error traduciendo: ... too many requests`
**Causa:** el endpoint web de Google **bloquea el IP del servidor** (throttling anti-scraping persistente, no una cuota diaria). Afecta solo al flujo manual `news_man` (`article_from_news.py`); en el pipeline principal ya no debería aparecer.

**Solución:** para el flujo manual, usar API oficial de Google Cloud Translation con clave, o ArgoMT local; el pipeline principal no necesita nada.

### 7. `[COQUI TTS] Error: RemoteDisconnected` + `corrupted size vs. prev_size` en el log del TTS
**Causa:** el proceso del servidor TTS (PyTorch/XTTS) se corrompió de memoria y se cayó a mitad de un fragmento; Docker lo reinicia automáticamente (`restart: unless-stopped`).

**Solución:** es un incidente puntual y el pipeline salta el fragmento sin bloquearse. Si se repite con frecuencia, reciclar el contenedor periódicamente (el modelo va en modo carga bajo demanda, el reinicio es barato). Verificar: `docker logs coqui-tts-server | tail -20` y `docker inspect --format '{{.RestartCount}}' $(docker ps -q -f name=coqui-tts-server)`.

### 8. `[FACEBOOK] video_path: None` (log INFO)
**Causa:** el vídeo no se generó (p. ej. la noticia no tenía imagen válida y el pool `/tmp/images` estaba vacío) o el contenedor corría código anterior a `feat(video)`. No es un error: Facebook publica la imagen como fallback.

**Solución:** el vídeo usa la imagen enriquecida del artículo, descargada al pool compartido `/tmp/images` (caché por md5; SVG y no-raster se rechazan). Para un fallback siempre disponible, dejar una JPG/PNG en `/tmp/images`.

## Verificar Cada Paso Individualmente

```bash
# 1. RSS
curl -X POST http://localhost:8000/rss

# 2. Verify
curl -X POST http://localhost:8000/verify

# 3. Soft verify
curl -X POST http://localhost:8000/soft

# 4. Articles
curl -X POST http://localhost:8000/article

# 5. Content
curl -X POST http://localhost:8000/content

# Ver MongoDB después de cada paso:
docker exec -it news_bot_app mongosh "mongodb://mongodb:27017"
use appdb
db.generated_articles.countDocuments()
db.generated_posts.countDocuments()
```

## Ejecución Completa del Pipeline

```bash
curl -X POST http://localhost:8000/pipeline

# Luego revisar los logs
docker logs news_bot_app --tail 500 | grep "\[PIPELINE\]"
```

## Notas Importantes

- El pipeline ahora llama a `main_pipeline()` del CLI, que tiene toda la lógica
- El CLI incluye **transcripción de audio (TTS)** y **generación de videos**
- Todos los publishers (`run()`) se llaman directamente desde el pipeline
- Los datos fluyen a través de MongoDB entre pasos

## Si Nada Funciona

1. **Revisar MongoDB está corriendo**: 
   ```bash
   docker ps | grep mongo
   ```

2. **Revisar conexión a MongoDB**:
   ```bash
   docker logs news_bot_app | grep "mongo\|database"
   ```

3. **Verificar credenciales de LLM** (Gemini, OpenAI, etc):
   ```bash
   docker exec news_bot_app env | grep AI_PROVIDER
   ```

4. **Revisar los logs completos del paso que falla**:
   ```bash
   docker logs news_bot_app -f  # Sigue los logs en vivo
   ```
