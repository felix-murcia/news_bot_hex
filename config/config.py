# config/config.py
# Backward compatibility - imports from new settings module

from config.settings import Settings

# Re-export for backward compatibility
BASE_DIR = Settings.BASE_DIR
MODEL_PATH = Settings.LOCAL_MODEL_PATH

MODEL_PARAMS_CONTENT = Settings.MODEL_PARAMS_CONTENT
MODEL_PARAMS_ARTICLE = Settings.MODEL_PARAMS_ARTICLE
MODEL_PARAMS_THREAD = Settings.MODEL_PARAMS_THREAD

API_KEYS = Settings.API_KEYS
FILTERS = Settings.NEWS_FILTERS
TRUSTED_SOURCES = Settings.TRUSTED_SOURCES
POST_LIMITS = Settings.POST_LIMITS

WHISPER_MODEL = Settings.WHISPER_MODEL
ALLOWED_VIDEO_DOMAINS = Settings.ALLOWED_VIDEO_DOMAINS

GEMINI_CONFIG = Settings.GEMINI_CONFIG
