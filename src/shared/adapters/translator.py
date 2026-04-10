import re
import hashlib
import os
import logging
from typing import List, Optional
from deep_translator import GoogleTranslator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")

CACHE_DIR = os.path.join("data", "cache", "translations")
os.makedirs(CACHE_DIR, exist_ok=True)

_translator = None


def _get_translator():
    global _translator
    if _translator is None:
        _translator = GoogleTranslator(source="auto", target="es")
    return _translator


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest() + ".txt"


def _is_probably_spanish(text: str) -> bool:
    palabras = re.findall(r"\w+", text.lower())
    if not palabras:
        return False
    comunes_es = {
        "el",
        "la",
        "de",
        "que",
        "en",
        "y",
        "a",
        "los",
        "del",
        "se",
        "un",
        "por",
        "con",
        "no",
        "una",
        "es",
        "al",
        "le",
        "lo",
        "las",
        "les",
    }
    ratio = sum(1 for w in palabras[:60] if w in comunes_es) / min(len(palabras), 60)
    return ratio > 0.25


def _split_into_chunks(text: str, max_chars: int = 4800) -> List[str]:
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""
    paragraphs = re.split(r"\n\s*\n|\n", text)

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 1 <= max_chars:
            current += ("\n\n" if current else "") + para
        else:
            if current:
                chunks.append(current)
            if len(para) > max_chars:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= max_chars:
                        current += (" " if current else "") + sent
                    else:
                        if current:
                            chunks.append(current)
                        current = sent
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


def translate_text(text: str, target_lang: str = "es") -> str:
    if not text or not text.strip():
        return text

    if _is_probably_spanish(text):
        logger.info("[TRANSLATOR] Texto ya está en español, omitiendo traducción")
        return text

    cache_file = os.path.join(CACHE_DIR, f"{_cache_key(text)}_{target_lang}.txt")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            logger.info("[TRANSLATOR] Traducción obtenida de caché")
            return f.read()

    try:
        chunks = _split_into_chunks(text, max_chars=4500)
        translated_chunks = []

        for i, chunk in enumerate(chunks):
            logger.info(f"[TRANSLATOR] Traduciendo chunk {i + 1}/{len(chunks)}...")
            translator = _get_translator()
            result = translator.translate(chunk)
            if result:
                translated_chunks.append(result)
            else:
                translated_chunks.append(chunk)

        full_translation = "\n\n".join(translated_chunks)

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(full_translation)
        except Exception:
            pass

        return full_translation

    except Exception as e:
        logger.error(f"[TRANSLATOR] Error traduciendo: {e}")
        return text
