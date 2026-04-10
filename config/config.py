# config/config.py
import os
from dotenv import load_dotenv

# Cargar variables desde .env
load_dotenv()

# === Ruta del modelo GGUF unificado ===
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "Llama-3.2-8B-Instruct-Q4_K_M.gguf")

# === Parámetros específicos para generación de contenido (content_generator) ===
MODEL_PARAMS_CONTENT = {
    "n_ctx": 3072,          # Llama‑3.2 soporta más contexto, aprovecha hasta 3K tokens
    "n_gpu_layers": 26,     # confirmado como óptimo en tu Jetson
    "n_batch": 64,          # estable; puedes probar 128 si quieres, pero 64 es seguro
    "max_tokens_tweet": 120, # suficiente para 280 caracteres (~70 tokens)
    "max_tokens_thread": 300,# para hilos (~1200 caracteres)
    "temperature": 0.35,    # un poco más bajo: más factual, menos divagación
    "top_p": 0.9,           # más diversidad que 0.85, sin perder control
    "top_k": 40,            # mantener bajo para foco
    "repeat_penalty": 1.15, # suavizar un poco, evita repeticiones sin cortar demasiado
}

# === Parámetros específicos para generación del articulo (article_generator) ===
MODEL_PARAMS_ARTICLE = {
    "max_tokens": 1024,
    "temperature": 0.6,       # un poco más alto para variedad
    "top_p": 0.9,
    "top_k": 40,
    "repetition_penalty": 1.2, # evita repetir frases
    "presence_penalty": 0.6    # incentiva nuevas ideas
}

# Parámetros específicos para generación de hilos (thread_generator)
MODEL_PARAMS_THREAD = {
    "temperature": 0.4,     # más factual, menos inventiva
    "top_p": 0.9,
    "top_k": 50,
    "max_tokens": 1500      # un poco más largo, hasta 7–8 tweets completos
}

# === Claves de API (todas desde variables de entorno) ===
API_KEYS = {
    'newsapi': os.getenv("NEWSAPI_KEY"),
    'census': os.getenv("CENSUS_API_KEY"),
    'grok': os.getenv("GROK_API_KEY"),
    'x_api_key': os.getenv("X_API_KEY"),
    'x_api_secret': os.getenv("X_API_SECRET"),
    'x_access_token': os.getenv("X_ACCESS_TOKEN"),
    'x_access_secret': os.getenv("X_ACCESS_SECRET"),
    'x_bearer_token': os.getenv("X_BEARER_TOKEN")
}

# === Filtros para NewsAPI ===
FILTERS = {
    'exclude_sources': [
        'el-mundo', 'el-pais', 'abc-news-es', 'la-vanguardia',
        '20-minutos', 'marca', 'as', 'sport',
        'news24'
    ],
    'q': '',
    'pageSize': 50,
    'page': 1,
    'keywords': [
        'news', 'update', 'international', 'world', 'crisis', 'conflict',
        'violence', 'economy', 'politics', 'population', 'regulation',
        'wildlife', 'marine', 'murder', 'attack', 'stock', 'futures'
    ]
}

# === Fuentes confiables para verificación ===
TRUSTED_SOURCES = [
    "AP News", "Reuters", "Bloomberg.com", "BBC News", "NBC News"
]

POST_LIMITS = {
    "x": 260,
    "bluesky": 250,
    "mastodon": 450
}

WHISPER_MODEL = "medium"
ALLOWED_VIDEO_DOMAINS = ["facebook.com", "twitter.com", "youtube.com"]

# Gemini
# Modelos disponibles:
# models/gemini-2.5-flash
# models/gemini-2.0-flash-001
# models/gemini-flash-latest
# models/gemini-2.5-flash-lite
# models/imagen-4.0-ultra-generate-001
# models/imagen-4.0-fast-generate-001
# models/veo-2.0-generate-001
# models/veo-3.0-generate-001
# models/veo-3.0-fast-generate-001
# models/veo-3.1-generate-preview
# models/veo-3.1-fast-generate-preview
# models/gemini-2.0-flash-live-001
# models/gemini-live-2.5-flash-preview
# models/gemini-2.5-flash-live-preview
# models/gemini-2.5-flash-native-audio-latest
# models/gemini-2.5-flash-native-audio-preview-09-2025
GEMINI_CONFIG = {
    # API Key (se lee de .env)
    'api_key': os.getenv("GEMINI_API_KEY", ""),
    
    # Modelo a usar
    'model_name': 'gemini-2.5-flash-lite',
    
    # Parámetros de generación
    'temperature': 0.7,
    'top_p': 0.9,
    'max_output_tokens': 5000,
    
    # Control de costes
    'enable_cost_tracking': True,
    'max_cost_per_month_eur': 5.0,  # Límite de seguridad
    
    # Configuración avanzada
    'timeout': 30,  # segundos
    'retry_attempts': 2,
}