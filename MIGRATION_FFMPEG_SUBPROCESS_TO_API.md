# FFmpeg Subprocess → ffmpeg-api Migration

## Status: ✅ FASE 1 COMPLETADA

Migration of all ffmpeg subprocess calls from news_bot_hex to ffmpeg-api microservice.

---

## Changes Implemented

### ffmpeg-api Service (`../ffmpeg-cuda/`)

**3 new endpoints added to `src/modules/audio_routes.py`:**

#### 1. `/audio/post-process` (POST)
- **Purpose**: Multi-step audio enhancement for TTS artifacts
- **Steps**: Normalization → Breathing removal → Plosive stabilization → Compression
- **Input**: 
  ```json
  {
    "path": "/tmp/audio.wav",
    "normalize": true,
    "remove_breathing": true,
    "stabilize_plosives": true,
    "noise_gate_threshold": -40.0
  }
  ```
- **Output**: Binary WAV audio data
- **Service**: `AudioPostProcessor` in `audio_helper/audio_post_processor.py`

#### 2. `/audio/apply-atempo` (POST)
- **Purpose**: Speed adjustment without pitch change using atempo filter
- **Input**:
  ```json
  {
    "path": "/tmp/audio.wav",
    "tempo_factor": 1.2
  }
  ```
- **Output**: Binary WAV audio data
- **Service**: `AudioTempoAdjuster` in `audio_helper/audio_tempo_adjuster.py`

#### 3. `/audio/concatenate` (POST)
- **Purpose**: Lossless concatenation of multiple audio files
- **Input**:
  ```json
  {
    "paths": ["/tmp/audio1.mp3", "/tmp/audio2.mp3", ...],
    "output_format": "mp3"
  }
  ```
- **Output**: Binary audio data in requested format
- **Service**: `AudioConcatenator` in `audio_helper/audio_concatenator.py`

**New services created:**
- `audio_helper/audio_post_processor.py` (349 lines)
- `audio_helper/audio_tempo_adjuster.py` (129 lines)
- `audio_helper/audio_concatenator.py` (163 lines)

**Config updates:**
- `src/modules/config.py`: Added `AUDIO_PROCESSING_TIMEOUT` and `AUDIO_CONCATENATION_TIMEOUT`

---

### news_bot_hex Service

**Files migrated from subprocess to HTTP:**

#### 1. `src/shared/adapters/audio_post_processor.py`
- **Before**: 4 subprocess.run() calls for:
  - Loudness normalization (ffmpeg)
  - Breathing artifact removal (ffmpeg + fallback)
  - Plosive stabilization (ffmpeg)
  - Compression (ffmpeg)
- **After**: Single HTTP call to `/audio/post-process`
- **Refactoring**: Replaced entire processing pipeline with HTTP request
- **Lines removed**: ~150 subprocess code
- **Lines added**: ~30 HTTP call code

#### 2. `src/shared/adapters/coqui_tts_adapter.py`
- **Before**: subprocess.run() call for atempo filter
- **After**: HTTP call to `/audio/apply-atempo` via new `_apply_atempo_filter()` method
- **Removed**: `import subprocess`
- **Added**: `_apply_atempo_filter()` method (40 lines)

#### 3. `src/shared/application/usecases/tts_from_article.py`
- **Before**: subprocess.run() call for audio concatenation with ffmpeg concat demuxer
- **After**: HTTP call to `/audio/concatenate`
- **Removed**: `import subprocess`
- **Added**: `import requests, from config.settings import Settings`
- **Refactored**: `concatenate_audio_files()` function (original: 35 lines → new: 50 lines)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│           news_bot_hex (Application)                │
├─────────────────────────────────────────────────────┤
│                                                     │
│  • audio_post_processor.py  ────→ HTTP POST        │
│  • coqui_tts_adapter.py     ────→ HTTP POST        │
│  • tts_from_article.py      ────→ HTTP POST        │
│                                                     │
└────────────┬────────────────────────────────────────┘
             │
             │ HTTP Requests (port 8082)
             │
┌────────────▼────────────────────────────────────────┐
│           ffmpeg-api (Microservice)                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  • /audio/post-process   ← AudioPostProcessor      │
│  • /audio/apply-atempo   ← AudioTempoAdjuster      │
│  • /audio/concatenate    ← AudioConcatenator       │
│                                                     │
│  All using:                                         │
│  • FFmpegExecutor (subprocess management)           │
│  • FileHandler (temp file management)               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Verification Checklist

### ffmpeg-api Service
- [ ] Verify services imported in `audio_routes.py`
- [ ] Check new endpoints registered in Flask app
- [ ] Test `/audio/post-process` with test WAV file
- [ ] Test `/audio/apply-atempo` with tempo_factor=1.5
- [ ] Test `/audio/concatenate` with multiple MP3s

### news_bot_hex Service
- [ ] Verify Settings.FFMPEG_API_URL is configured
- [ ] Check audio_post_processor HTTP calls
- [ ] Check coqui_tts_adapter HTTP calls
- [ ] Verify no subprocess imports in modified files

### Integration
- [ ] Run news pipeline with TTS enabled
- [ ] Check audio post-processing logs
- [ ] Verify concatenated audio quality
- [ ] Monitor ffmpeg-api service logs

---

## Error Handling

Both services implement graceful error handling:
- **Timeout**: 300s for audio operations
- **Connection errors**: Logged, non-blocking
- **HTTP errors**: Logged with status codes
- **File I/O errors**: Graceful fallbacks

---

## Performance

### Expected Overhead
- Network latency: ~10-50ms per operation (local Docker)
- Subprocess elimination: Removes OS context switch overhead
- Net impact: Negligible on overall pipeline performance

### Concurrent Operations
- Each request uses unique temp_id (UUID)
- No file conflicts between concurrent requests
- Connection pooling via requests library

---

## Next Steps

1. **Testing**: Run integration tests with full TTS pipeline
2. **Monitoring**: Add metrics collection for API calls
3. **Optimization**: Consider request batching if performance issues arise
4. **Documentation**: Update architecture docs with microservice pattern

---

## Files Summary

| File | Type | Changes |
|------|------|---------|
| `audio_post_processor.py` | ✅ Migrated | subprocess → HTTP |
| `coqui_tts_adapter.py` | ✅ Migrated | subprocess → HTTP |
| `tts_from_article.py` | ✅ Migrated | subprocess → HTTP |
| `audio_converter.py` | ✅ Already using HTTP | No change |
| `video_generator.py` | ✅ Already using HTTP | No change |

---

## Rollback Plan

If issues arise with ffmpeg-api connectivity:

1. audio_post_processor.py: Has try/except with graceful degradation
2. coqui_tts_adapter.py: Continues without atempo if service unavailable
3. tts_from_article.py: Continues without concatenation if service unavailable

All three services are non-blocking failures (pipeline continues).
