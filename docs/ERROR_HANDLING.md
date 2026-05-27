# Error Handling System

This document describes how the error handling system works between the backend and frontend.

## Backend Error Handling

### Creating Errors

The backend uses structured error responses via the `http_error()` function:

```python
from src.news.entrypoints.api.error_handler import http_error, get_error_message

# Get user-friendly message for error code
msg, details = get_error_message("CONTENT_EXTRACTION_FAILED")

# Raise structured error
raise http_error(
    status_code=400,
    error_code="CONTENT_EXTRACTION_FAILED",
    message=msg,
    exception=e,  # Original exception (logged with traceback)
    details=details,  # Additional context for user
    context={"url": url}  # Data logged but not shown to user
)
```

### Error Response Structure

All API errors return a consistent JSON structure:

```json
{
  "status": "error",
  "message": "User-friendly error message",
  "error_code": "CONTENT_EXTRACTION_FAILED",
  "details": "Additional context for the user",
  "context": {...}  // Only logged, never sent to user
}
```

### Available Error Codes

- **INVALID_URL** - URL is empty or invalid
- **CONTENT_EXTRACTION_FAILED** - Could not extract content from webpage
- **CONTENT_TOO_SHORT** - Article content is too short (< 100 characters)
- **ARTICLE_GENERATION_FAILED** - AI model failed to generate article
- **TWEET_GENERATION_FAILED** - Tweet generation or truncation failed
- **TTS_GENERATION_FAILED** - Text-to-speech generation failed
- **VIDEO_GENERATION_FAILED** - Video generation from audio failed
- **DATABASE_ERROR** - Database connection or query failed
- **SERVICE_UNAVAILABLE** - External service (API, TTS, etc.) is down
- **INVALID_REQUEST** - Invalid request parameters
- **PIPELINE_ERROR** - Generic pipeline processing error

### Logging

- **User-facing message**: Simple, actionable information
- **Backend logs**: Full exception traceback and context
- **No sensitive data**: URLs, credentials, etc. are logged with context, not in message

## Frontend Error Handling

### Using Error States

The `LogPanel` component automatically displays errors:

```tsx
import { LogPanel } from "../../components/LogPanel";

// In your component:
const mutation = useMutation({...});

// LogPanel handles both structured and string errors
<LogPanel 
  loading={mutation.isPending}
  response={mutation.data}
  error={mutation.error}
/>
```

### The `useErrorHandler` Hook

For advanced error handling:

```tsx
import { useErrorHandler } from "../../hooks/useErrorHandler";

function MyComponent() {
  const { error, isError, handleError, clearError } = useErrorHandler();

  const handleRequest = async () => {
    try {
      const data = await api.post("/endpoint", {...});
    } catch (err) {
      handleError(err);  // Extracts structured error
    }
  };

  return (
    <>
      {isError && <ErrorAlert 
        message={error!.message}
        details={error!.details}
        errorCode={error!.error_code}
        onDismiss={clearError}
      />}
    </>
  );
}
```

### ErrorAlert Component

Display errors with a consistent UI:

```tsx
import { ErrorAlert } from "../../components/ErrorAlert";

<ErrorAlert
  message="Could not extract content"
  details="The website may be blocked or inaccessible"
  errorCode="CONTENT_EXTRACTION_FAILED"
  onDismiss={() => {}}
  variant="error"  // or "warning"
/>
```

## Flow Example

1. User submits a URL via "Procesar URL Concreta"
2. Frontend sends POST to `/news/process_url`
3. Backend attempts to extract content
4. Content extraction fails (network error, site blocked, etc.)
5. Backend logs full exception with traceback
6. Backend returns:
   ```json
   {
     "status": "error",
     "message": "No se pudo extraer el contenido",
     "error_code": "CONTENT_EXTRACTION_FAILED",
     "details": "El sitio web puede estar bloqueado o no accesible"
   }
   ```
7. Frontend extracts error via `mutationState(mutation)`
8. `LogPanel` displays `ErrorAlert` with the user-friendly message
9. User sees: "No se pudo extraer el contenido" with helpful details
10. Developer can check server logs for full exception details

## Best Practices

### For Backend Developers

1. Always use `get_error_message()` for consistency
2. Include the original exception for logging
3. Use `context` for debugging info (never shown to user)
4. Add meaningful `details` for better UX
5. Choose the most specific error code available

### For Frontend Developers

1. Let `LogPanel` handle most error display
2. Use `ErrorAlert` only for custom error handling
3. Always provide `onDismiss` callback to allow users to close errors
4. Don't modify error messages from backend
5. Log any extraction errors for debugging

## Extending Error Codes

To add a new error code:

1. Add to `ERROR_CODES` dict in `error_handler.py`:
   ```python
   "NEW_ERROR": ("User message", "Helper details")
   ```

2. Use in endpoints:
   ```python
   msg, details = get_error_message("NEW_ERROR")
   raise http_error(
       status_code=400,
       error_code="NEW_ERROR",
       message=msg,
       details=details,
       exception=e
   )
   ```

3. Frontend automatically handles it (no changes needed!)
