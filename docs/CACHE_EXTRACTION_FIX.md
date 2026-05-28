# Cache & Jina Extraction Flow Analysis

## Problem Identified

You were right to question the flow. The issue was:

**"Procesar URL Concreta" should show the complete pipeline starting from content extraction with Jina, but logs of Jina extraction were not visible.**

### Root Cause

In `news_to_news.py`, the `_extract_content()` method checks the **cache first** before calling Jina:

```python
def _extract_content(self, url: str) -> tuple[str, Path]:
    cached = self._load_from_cache(url)
    if cached:
        logger.info("[NEWS_TO_NEWS] Usando contenido desde caché")
        return cached  # ← Returns here, Jina never called!
    
    content, method = self.content_extractor.extract(url)  # ← Jina called here
```

When a URL has been processed before (within 24 hours), the cached content is returned immediately. This means:

1. **Jina is never called** → No `[JINA] Extrayendo...` logs appear
2. **The pipeline appears incomplete** to the user
3. **Debugging is difficult** because you can't see if Jina extraction is working

From the logs on 2026-05-27 17:31:53, this is exactly what happened:
```
[CACHE] Cargado desde caché: 14200 chars (0.4h)
[NEWS_TO_NEWS] Usando contenido desde caché
[NEWS_TO_NEWS] Saltó directamente a generación de artículo...
```

## Solution Implemented

Added a **`force_extract` option** that allows you to bypass the cache and see the complete pipeline:

### Backend Changes

1. **ProcessUrlRequest** now accepts:
   ```python
   force_extract: bool = False  # Skip cache and force Jina extraction
   ```

2. **NewsToNewsUseCase** respects this flag:
   ```python
   def __init__(self, ..., force_extract: bool = False):
       self.force_extract = force_extract
   
   def _extract_content(self, url: str):
       if not self.force_extract:  # Only check cache if NOT forcing
           cached = self._load_from_cache(url)
           if cached:
               return cached
       
       # Always call Jina if force_extract=True
       content, method = self.content_extractor.extract(url)
       return content, cache_path
   ```

### Frontend Changes

Added checkbox in "Procesar URL Concreta":
- **"Forzar extracción con Jina"** checkbox
- When checked: Cache is skipped, fresh Jina extraction happens
- Users see complete log flow: `[JINA] Extrayendo...` → `[JINA] Exito`

## How It Works Now

### Default Behavior (force_extract = false)
```
Process URL → Check Cache → If found, return cached content
           → If not found, call Jina → Use fresh content
```

### With Force Extract (force_extract = true)
```
Process URL → Skip Cache → Always call Jina → Use fresh content
```

## Viewing the Complete Pipeline

To see the full extraction pipeline with Jina logs:

1. Open "Procesar URL Concreta" section
2. Check the **"Forzar extracción con Jina"** checkbox
3. Enter URL and click "Procesar URL"
4. You'll now see complete logs:
   ```
   [NEWS_TO_NEWS] Iniciando procesamiento de: https://...
   [NEWS_TO_NEWS] Forzando extracción fresca (omitiendo caché)
   [JINA] Extrayendo https://...
   [JINA] Exito (14200 chars)
   [ARTICLE_NEWS] Iniciando generación desde noticia...
   [ARTICLE_NEWS] Artículo generado: 7 párrafos...
   [NEWS_TO_NEWS] Tweet generado: ...
   [NEWS_TO_NEWS] Generando audio TTS...
   ...
   ```

## Benefits

✅ **Visibility**: See the complete pipeline flow  
✅ **Debugging**: Verify Jina extraction is working  
✅ **Performance**: Cache still used by default for faster reprocessing  
✅ **Freshness**: Can force fresh extraction when needed  
✅ **Testing**: Easy to test with different URLs repeatedly  

## When to Use force_extract

- **First test of a URL**: Use force_extract to verify extraction works
- **Debugging extraction issues**: See Jina logs to diagnose problems
- **Updating content**: If URL content changed, force refresh
- **Regular processing**: Leave unchecked (uses cache for performance)
