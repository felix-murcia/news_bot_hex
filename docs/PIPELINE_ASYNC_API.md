# Pipeline Asíncrono - API de Polling

## Problema Resuelto
El pipeline tarda más de 5 minutos (especialmente con transcripción local Coqui TTS), causando timeouts (504) en el cliente. Ahora usa polling para que el frontend sepa que el proceso sigue vivo.

## Flujo de Uso

### 1. Iniciar Pipeline
**Endpoint:** `POST /pipeline`

**Respuesta:**
```json
{
  "status": "ok",
  "message": "Pipeline started",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### 2. Polling para Status
**Endpoint:** `GET /pipeline/status/{job_id}`

**Respuesta mientras está en progreso:**
```json
{
  "status": "ok",
  "message": "Pipeline en progreso",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "progress": 45,
    "steps": [
      {
        "name": "RSS Fetch",
        "status": "ok",
        "timestamp": "2026-05-21T11:30:00.000Z"
      },
      {
        "name": "Full Verification",
        "status": "ok",
        "timestamp": "2026-05-21T11:30:30.000Z"
      },
      {
        "name": "Generate Posts",
        "status": "ok",
        "timestamp": "2026-05-21T11:31:00.000Z"
      },
      {
        "name": "Generate Articles",
        "status": "running",
        "timestamp": "2026-05-21T11:31:30.000Z"
      },
      {
        "name": "Fetch Images",
        "status": "pending",
        "timestamp": null
      }
    ],
    "error": null,
    "created_at": "2026-05-21T11:30:00.000Z",
    "started_at": "2026-05-21T11:30:00.500Z",
    "completed_at": null
  }
}
```

**Respuesta cuando está completado:**
```json
{
  "status": "ok",
  "message": "Pipeline completado exitosamente",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "progress": 100,
    "steps": [
      ...todos los pasos con "ok"...
    ],
    "error": null,
    "created_at": "2026-05-21T11:30:00.000Z",
    "started_at": "2026-05-21T11:30:00.500Z",
    "completed_at": "2026-05-21T12:05:30.000Z"
  }
}
```

**Respuesta si falló:**
```json
{
  "status": "ok",
  "message": "Error: [description]",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "failed",
    "progress": 60,
    "steps": [...],
    "error": "Error message here",
    "created_at": "2026-05-21T11:30:00.000Z",
    "started_at": "2026-05-21T11:30:00.500Z",
    "completed_at": "2026-05-21T12:05:30.000Z"
  }
}
```

## Estados Posibles

| Estado | Significado |
|--------|------------|
| `pending` | Job creado pero no iniciado |
| `running` | Pipeline en ejecución |
| `completed` | Pipeline finalizó exitosamente |
| `failed` | Pipeline finalizó con error |

## Estados de Pasos

| Estado | Significado |
|--------|------------|
| `running` | Paso en ejecución |
| `ok` | Paso completado exitosamente |
| `error` | Paso falló pero pipeline continuó |
| `skipped` | Paso fue saltado (ej: audio si no hay artículos) |

## Implementación en Frontend (React)

```typescript
// 1. Iniciar pipeline
const startPipeline = async () => {
  const response = await fetch('/api/pipeline', { method: 'POST' });
  const data = await response.json();
  const jobId = data.data.job_id;
  
  // Guardar jobId en estado
  setJobId(jobId);
  setIsRunning(true);
  
  // Iniciar polling
  pollPipelineStatus(jobId);
};

// 2. Polling
const pollPipelineStatus = async (jobId: string) => {
  const interval = setInterval(async () => {
    const response = await fetch(`/api/pipeline/status/${jobId}`);
    const data = await response.json();
    const job = data.data;
    
    // Actualizar UI
    setProgress(job.progress);
    setSteps(job.steps);
    setMessage(job.message);
    
    // Si está completo, detener polling
    if (job.status === 'completed' || job.status === 'failed') {
      clearInterval(interval);
      setIsRunning(false);
    }
  }, 2000); // Polling cada 2 segundos
};
```

## Pasos del Pipeline

El pipeline ejecuta estos 10 pasos secuencialmente:

1. **RSS Fetch** - Descarga artículos de fuentes RSS
2. **Full Verification** - Verifica y califica noticias
3. **Generate Posts** - Genera tweets/posts para redes sociales
4. **Generate Articles** - Genera artículos profesionales
5. **Fetch Images** - Busca imágenes (Unsplash + Google)
6. **Enrich Images** - Enriquece contenido con imágenes
7. **Generate Audio** - Convierte artículos a audio (TTS)
8. **Generate Video** - Crea videos desde audio
9. **Publish WordPress** - Publica en WordPress
10. **Publish Social** - Publica en Facebook, Bluesky, Mastodon

## Timing Esperado

- RSS Fetch: ~10 segundos
- Verification: ~20 segundos
- Generate Posts: ~10 segundos
- Generate Articles: ~30 segundos
- Fetch Images: ~15 segundos
- Enrich Images: ~5 segundos
- **Generate Audio (Coqui TTS local): ~5-10 minutos** ⏰
- Generate Video: ~2-5 minutos
- Publish WordPress: ~10 segundos
- Publish Social: ~15 segundos

**Total esperado: 6-17 minutos** (depende principalmente de Coqui TTS)

## Recomendaciones para Frontend

1. **Polling**: Usar intervalo de 2-3 segundos
2. **Timeout**: No usar timeout menor a 20 minutos
3. **UI Feedback**:
   - Mostrar barra de progreso
   - Listar pasos con sus estados
   - Mostrar timestamp de cada paso
   - Mensaje: "Generando audio (esto puede tomar algunos minutos)..."
4. **Error Handling**: Si `status === 'failed'`, mostrar `error` al usuario
5. **Limpieza**: Limpiar jobs completados después de 24 horas

## Curl de Prueba

```bash
# 1. Iniciar
JOB_ID=$(curl -s -X POST http://localhost:8000/pipeline | jq -r '.data.job_id')
echo "Job ID: $JOB_ID"

# 2. Polling (ejecutar varias veces)
curl http://localhost:8000/pipeline/status/$JOB_ID | jq '.data | {status, progress, steps}'

# 3. Ver progreso final
watch -n 2 "curl -s http://localhost:8000/pipeline/status/$JOB_ID | jq '.data | {status, progress, steps[-1]}'"
```
