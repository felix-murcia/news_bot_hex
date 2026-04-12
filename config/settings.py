"""Application settings with centralized configuration.

All hardcoded values and configuration should be defined here,
loaded from environment variables or config files.
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Centralized application settings."""

    # === Base Paths ===
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    DATA_DIR = BASE_DIR / "data"
    CACHE_DIR = DATA_DIR / "cache"
    MODELS_DIR = BASE_DIR / "models"
    IMAGES_DIR = DATA_DIR / "images"

    # === WordPress Configuration ===
    WP_HOSTING_API_BASE = os.getenv("WP_HOSTING_API_BASE", "https://api.nbes.blog")
    WP_HOSTING_JWT_TOKEN = os.getenv("WP_HOSTING_JWT_TOKEN", "")
    WP_DEFAULT_IMAGE_URL = os.getenv("WP_DEFAULT_IMAGE_URL", "https://api.nbes.blog/image-310/")
    WP_SITE_URL = os.getenv("WP_SITE_URL", "https://nbes.blog")
    WP_API_URL = os.getenv("WP_API_URL", f"{WP_HOSTING_API_BASE}/wp-json/wp/v2")
    WP_DEFAULT_CATEGORY = os.getenv("WP_DEFAULT_CATEGORY", "Noticias")
    WP_DEFAULT_IMAGE_ENDPOINT = os.getenv("WP_DEFAULT_IMAGE_ENDPOINT", "/image-310/")

    # === Facebook Configuration ===
    FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
    FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
    FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID", "")
    FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "")
    FACEBOOK_GRAPH_API_VERSION = os.getenv("FACEBOOK_GRAPH_API_VERSION", "v23.0")
    FACEBOOK_GRAPH_API_BASE = os.getenv("FACEBOOK_GRAPH_API_BASE", "https://graph.facebook.com")

    # === Bluesky Configuration ===
    BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE", "")
    BLUESKY_APP_PASSWORD = os.getenv("BLUESKY_APP_PASSWORD", "")
    BLUESKY_PDS_URL = os.getenv("BLUESKY_PDS_URL", "https://bsky.social")

    # === Mastodon Configuration ===
    MASTODON_INSTANCE_URL = os.getenv("MASTODON_INSTANCE_URL", "https://mastodon.social")
    MASTODON_ACCESS_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN", "")
    MASTODON_API_BASE = os.getenv("MASTODON_API_BASE", None)  # Will be derived from instance URL

    # === Unsplash Configuration ===
    UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
    UNSPLASH_API_URL = os.getenv("UNSPLASH_API_URL", "https://api.unsplash.com/search/photos")
    UNSPLASH_ORIENTATION = os.getenv("UNSPLASH_ORIENTATION", "landscape")
    UNSPLASH_PER_PAGE = int(os.getenv("UNSPLASH_PER_PAGE", "3"))

    # === Google Images Configuration ===
    GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
    GOOGLE_API_URL = os.getenv("GOOGLE_API_URL", "https://www.googleapis.com/customsearch/v1")

    # === Social Media Limits ===
    POST_LIMITS: Dict[str, int] = {
        "x": int(os.getenv("X_POST_LIMIT", "260")),
        "bluesky": int(os.getenv("BLUESKY_POST_LIMIT", "250")),
        "mastodon": int(os.getenv("MASTODON_POST_LIMIT", "450")),
    }

    # === AI Model Configuration ===
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openrouter").lower()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    OPENROUTER_AUTH_URL = os.getenv("OPENROUTER_AUTH_URL", "https://openrouter.ai/api/v1/auth/key")
    OPENROUTER_REFERER = os.getenv("OPENROUTER_REFERER", "http://nbes.blog")
    OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "news_bot")
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")

    # === Groq Transcription Configuration ===
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/audio/transcriptions")
    GROQ_TRANSCRIBE_MODEL = os.getenv("GROQ_TRANSCRIBE_MODEL", "whisper-large-v3-turbo")

    # === Local Model Configuration ===
    LOCAL_MODEL_PATH = os.getenv("LOCAL_MODEL_PATH", str(BASE_DIR / "models" / "Llama-3.2-8B-Instruct-Q4_K_M.gguf"))
    LOCAL_MODEL_N_CTX = int(os.getenv("LOCAL_MODEL_N_CTX", "3072"))
    LOCAL_MODEL_N_GPU_LAYERS = int(os.getenv("LOCAL_MODEL_N_GPU_LAYERS", "26"))
    LOCAL_MODEL_N_BATCH = int(os.getenv("LOCAL_MODEL_N_BATCH", "64"))

    # === Fake News Detection Model ===
    # Path for pre-trained classic validator model (TF-IDF + LogisticRegression)
    # Falls back to heuristic rules if no model is found
    FAKE_NEWS_MODEL_DIR = BASE_DIR / "models" / "news_validator"

    # === Model Parameters ===
    MODEL_PARAMS_CONTENT: Dict[str, Any] = {
        "n_ctx": int(os.getenv("MODEL_N_CTX", "3072")),
        "n_gpu_layers": int(os.getenv("MODEL_N_GPU_LAYERS", "26")),
        "n_batch": int(os.getenv("MODEL_N_BATCH", "64")),
        "max_tokens_tweet": int(os.getenv("MODEL_MAX_TOKENS_TWEET", "120")),
        "max_tokens_thread": int(os.getenv("MODEL_MAX_TOKENS_THREAD", "300")),
        "temperature": float(os.getenv("MODEL_TEMPERATURE", "0.35")),
        "top_p": float(os.getenv("MODEL_TOP_P", "0.9")),
        "top_k": int(os.getenv("MODEL_TOP_K", "40")),
        "repeat_penalty": float(os.getenv("MODEL_REPEAT_PENALTY", "1.15")),
    }

    MODEL_PARAMS_ARTICLE: Dict[str, Any] = {
        "max_tokens": int(os.getenv("ARTICLE_MAX_TOKENS", "1024")),
        "temperature": float(os.getenv("ARTICLE_TEMPERATURE", "0.6")),
        "top_p": float(os.getenv("ARTICLE_TOP_P", "0.9")),
        "top_k": int(os.getenv("ARTICLE_TOP_K", "40")),
        "repetition_penalty": float(os.getenv("ARTICLE_REPETITION_PENALTY", "1.2")),
        "presence_penalty": float(os.getenv("ARTICLE_PRESENCE_PENALTY", "0.6")),
    }

    MODEL_PARAMS_THREAD: Dict[str, Any] = {
        "temperature": float(os.getenv("THREAD_TEMPERATURE", "0.4")),
        "top_p": float(os.getenv("THREAD_TOP_P", "0.9")),
        "top_k": int(os.getenv("THREAD_TOP_K", "50")),
        "max_tokens": int(os.getenv("THREAD_MAX_TOKENS", "1500")),
    }

    # === Gemini Configuration ===
    GEMINI_CONFIG: Dict[str, Any] = {
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "model_name": GEMINI_MODEL,
        "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0.7")),
        "top_p": float(os.getenv("GEMINI_TOP_P", "0.9")),
        "max_output_tokens": int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "5000")),
        "enable_cost_tracking": os.getenv("GEMINI_ENABLE_COST_TRACKING", "true").lower() == "true",
        "max_cost_per_month_eur": float(os.getenv("GEMINI_MAX_COST_PER_MONTH_EUR", "5.0")),
        "timeout": int(os.getenv("GEMINI_TIMEOUT", "30")),
        "retry_attempts": int(os.getenv("GEMINI_RETRY_ATTEMPTS", "2")),
    }

    # === API Keys ===
    API_KEYS = {
        "newsapi": os.getenv("NEWSAPI_KEY"),
        "census": os.getenv("CENSUS_API_KEY"),
        "grok": os.getenv("GROK_API_KEY"),
        "x_api_key": os.getenv("X_API_KEY"),
        "x_api_secret": os.getenv("X_API_SECRET"),
        "x_access_token": os.getenv("X_ACCESS_TOKEN"),
        "x_access_secret": os.getenv("X_ACCESS_SECRET"),
        "x_bearer_token": os.getenv("X_BEARER_TOKEN"),
        "openrouter": os.getenv("OPENROUTER_API_KEY"),
        "gemini": os.getenv("GEMINI_API_KEY"),
        "unsplash": os.getenv("UNSPLASH_ACCESS_KEY"),
        "google_search": os.getenv("GOOGLE_SEARCH_API_KEY"),
        "facebook": os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN"),
        "mastodon": os.getenv("MASTODON_ACCESS_TOKEN"),
    }

    # === News API Filters ===
    NEWS_FILTERS: Dict[str, Any] = {
        "exclude_sources": os.getenv("NEWS_EXCLUDE_SOURCES", "el-mundo,el-pais,abc-news-es,la-vanguardia,20-minutos,marca,as,sport,news24").split(","),
        "q": os.getenv("NEWS_QUERY", ""),
        "pageSize": int(os.getenv("NEWS_PAGE_SIZE", "50")),
        "page": int(os.getenv("NEWS_PAGE", "1")),
        "keywords": os.getenv("NEWS_KEYWORDS", "news,update,international,world,crisis,conflict,violence,economy,politics,population,regulation,wildlife,marine,murder,attack,stock,futures").split(","),
    }

    # === Trusted Sources ===
    TRUSTED_SOURCES: List[str] = os.getenv("TRUSTED_SOURCES", "AP News,Reuters,Bloomberg.com,BBC News,NBC News").split(",")

    # === Copyright Risk Domains ===
    COPYRIGHT_DOMAINS: List[str] = os.getenv("COPYRIGHT_DOMAINS", "elpais.com,elmundo.es,20minutos.es,marca.com,as.com,cincodias.elpais.es,bbc.com").split(",")

    # === Video Copyright Domains ===
    VIDEO_COPYRIGHT_DOMAINS: List[str] = os.getenv("VIDEO_COPYRIGHT_DOMAINS", "youtube.com,youtu.be,tiktok.com,instagram.com,spotify.com,apple.com").split(",")

    # === Video Configuration ===
    ALLOWED_VIDEO_DOMAINS: List[str] = os.getenv("ALLOWED_VIDEO_DOMAINS", "facebook.com,twitter.com,youtube.com").split(",")

    # === Cache Configuration ===
    CACHE_MAX_AGE_HOURS = int(os.getenv("CACHE_MAX_AGE_HOURS", "6"))
    CACHE_CLEANUP_MAX_AGE_HOURS = int(os.getenv("CACHE_CLEANUP_MAX_AGE_HOURS", "72"))

    # === Retry Configuration ===
    RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "2.0"))
    RETRY_MAX_DELAY = float(os.getenv("RETRY_MAX_DELAY", "60.0"))

    # === Topic Normalization ===
    TOPIC_NORMALIZATION_MAP: Dict[str, str] = {
        "Audio": os.getenv("TOPIC_AUDIO", "Noticias"),
        "Podcast": os.getenv("TOPIC_PODCAST", "Noticias"),
        "Video": os.getenv("TOPIC_VIDEO", "Noticias"),
        "Política": os.getenv("TOPIC_POLITICA", "Noticias"),
        "Política internacional": os.getenv("TOPIC_POLITICA_INTERNACIONAL", "Noticias"),
    }

    # === Jina Reader Configuration ===
    JINA_API_URL = os.getenv("JINA_API_URL", "https://r.jina.ai/")
    JINA_API_KEY = os.getenv("JINA_API_KEY", "")

    # === MongoDB Configuration ===
    MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
    MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
    MONGO_USER = os.getenv("MONGO_USER", "")
    MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "news_bot")
    USE_MONGODB = os.getenv("USE_MONGODB", "true").lower() == "true"

    # === Deep Translator Configuration ===
    DEEP_TRANSLATOR_TARGET_LANG = os.getenv("DEEP_TRANSLATOR_TARGET_LANG", "es")
    DEEP_TRANSLATOR_SOURCE_LANG = os.getenv("DEEP_TRANSLATOR_SOURCE_LANG", "en")

    # === Spell Checker Configuration ===
    SPELL_CHECKER_LANG = os.getenv("SPELL_CHECKER_LANG", "es")

    @classmethod
    def ensure_directories(cls):
        """Create required directories if they don't exist."""
        for directory in [cls.DATA_DIR, cls.CACHE_DIR, cls.MODELS_DIR, cls.IMAGES_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_normalized_topic(cls, topic: str) -> str:
        """Normalize a topic to a standard category."""
        return cls.TOPIC_NORMALIZATION_MAP.get(topic, topic)


# Initialize directories on import
Settings.ensure_directories()
