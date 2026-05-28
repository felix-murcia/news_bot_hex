# Provider Validation Fix for "Procesar URL Concreta"

## Problem Identified

The "Procesar URL Concreta" feature was returning 500 errors when processing URLs. Root cause analysis revealed:

- **Frontend offered providers**: gemini, openai, anthropic, openrouter
- **Backend supported providers**: openrouter, gemini, local, mock

When users selected "openai" or "anthropic", the backend would reject them as unsupported, causing a 500 error with an unhelpful message.

## Solution Implemented

### Backend Changes (news_router.py)

1. **New Provider Validation Function**
   - Added `validate_provider()` helper function
   - Validates provider against `Settings.AI_ADAPTER_MAP`
   - Returns clear error message with available options

2. **New Endpoint: `/news/providers`**
   ```python
   GET /news/providers
   Returns: {"status": "ok", "data": {"providers": ["openrouter", "gemini", "local", "mock"]}}
   ```

3. **Improved Error Handling**
   - Provider validation in `/process_url` endpoint
   - Better error logging with error type information
   - Clear error messages for invalid providers

### Frontend Changes (NewsTab.tsx + news.ts API)

1. **New API Function**
   - `getSupportedProviders()` - Fetches list from backend on component mount

2. **Dynamic Provider List**
   - Replaces hardcoded `AI_PROVIDERS` constant
   - Fetches actual supported providers on mount
   - Updates all three provider selectors:
     - Article generation
     - Social content generation
     - URL processing

3. **Graceful Fallback**
   - If fetch fails, uses default provider list
   - Never breaks UI even if backend is unavailable

## How It Works Now

1. User opens "Procesar URL Concreta" section
2. NewsTab mounts and fetches `/news/providers`
3. Provider dropdowns display only actual supported options
4. User selects a valid provider (e.g., "gemini")
5. Request is sent and processed successfully

## Error Messages

If somehow an invalid provider is sent:
- **Status Code**: 400 (Bad Request)
- **Error Code**: INVALID_REQUEST
- **Message**: "Proveedor de IA no válido"
- **Details**: "Proveedor no soportado: openai. Disponibles: openrouter, gemini, local, mock"

## Testing

To verify the fix:
1. Open the interface
2. Navigate to "Procesar URL Concreta"
3. Check that only valid providers appear in the dropdown
4. Select a provider and test with a URL
5. Should work without 500 errors
