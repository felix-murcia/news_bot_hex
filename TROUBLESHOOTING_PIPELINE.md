# Troubleshooting: Pipeline No Publica

## Estado Actual del Pipeline
El pipeline ahora implementa 12 pasos completos (incluyendo audio y video como en el legacy):
1. ✅ RSS fetch
2. ✅ Full verification
3. ✅ Generate posts/tweets
4. ✅ Generate professional articles
5. ✅ Fetch images (Unsplash + Google)
6. ✅ Image enrichment
7. ✅ **Generate audio (TTS)**
8. ✅ **Generate videos from audio**
9. ✅ Publish to WordPress
10. ✅ Publish to Facebook
11. ✅ Publish to Bluesky
12. ✅ Publish to Mastodon

## Diagnóstico: Por Qué No Publica

### Paso 1: Verificar que hay noticias verificadas
```bash
# En el contenedor Docker, conectarse a MongoDB:
docker exec news_bot_hex-mongo-1 mongosh

# Dentro de mongosh:
use news_bot_db
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
docker logs news_bot_hex-api-1 --tail 200
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
docker logs news_bot_hex-api-1 | grep "VERIFIER\|VERIFY\|Error"
```

### 2. "No hay posts para procesar"
**Causa**: `run_content()` no está guardando en `generated_posts`

**Solución**: Verificar:
```bash
# Ejecutar solo content generation:
curl -X POST http://localhost:8000/content

# Ver logs:
docker logs news_bot_hex-api-1 | grep "CONTENT"
```

### 3. "No hay artículos para publicar"
**Causa**: `run_article()` no está generando/guardando artículos

**Solución**: Verificar:
```bash
# Ejecutar solo article generation:
curl -X POST http://localhost:8000/article

# Ver logs:
docker logs news_bot_hex-api-1 | grep "ARTICLE"
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
docker exec news_bot_hex-mongo-1 mongosh
use news_bot_db
db.generated_articles.countDocuments()
db.generated_posts.countDocuments()
```

## Ejecución Completa del Pipeline

```bash
curl -X POST http://localhost:8000/pipeline

# Luego revisar los logs
docker logs news_bot_hex-api-1 --tail 500 | grep "\[PIPELINE\]"
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
   docker logs news_bot_hex-api-1 | grep "mongo\|database"
   ```

3. **Verificar credenciales de LLM** (Gemini, OpenAI, etc):
   ```bash
   docker exec news_bot_hex-api-1 env | grep AI_PROVIDER
   ```

4. **Revisar los logs completos del paso que falla**:
   ```bash
   docker logs news_bot_hex-api-1 -f  # Sigue los logs en vivo
   ```
