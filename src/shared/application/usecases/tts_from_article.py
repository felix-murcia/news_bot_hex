"""Use case para generar audio TTS desde artículos."""

import re
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.logging_config import get_logger
from src.shared.domain.ports.tts_port import TTSPort
from src.shared.domain.ports.audio_converter_port import AudioConverterPort
from src.shared.adapters.tts_text_processor import TTSTextProcessor

logger = get_logger("shared.usecases.tts")

COQUI_TTS_CHAR_LIMIT = 239


def split_text_by_sentences(text: str, char_limit: int = COQUI_TTS_CHAR_LIMIT) -> List[str]:
    """Divide el texto en fragmentos respetando el límite de caracteres y oraciones."""
    if len(text) <= char_limit:
        return [text]

    sentences = re.split(r'(?<=[.!?])\s+', text)

    fragments = []
    current_fragment = ""

    for sentence in sentences:
        if len(sentence) > char_limit:
            if current_fragment:
                fragments.append(current_fragment)
                current_fragment = ""

            parts = re.split(r'(?<=[,:])\s+', sentence)
            for part in parts:
                if len(current_fragment) + len(part) + 1 <= char_limit:
                    if current_fragment:
                        current_fragment += " " + part
                    else:
                        current_fragment = part
                else:
                    if current_fragment:
                        fragments.append(current_fragment)
                    current_fragment = part
        else:
            test_fragment = current_fragment + " " + sentence if current_fragment else sentence
            if len(test_fragment) <= char_limit:
                current_fragment = test_fragment
            else:
                if current_fragment:
                    fragments.append(current_fragment)
                current_fragment = sentence

    if current_fragment:
        fragments.append(current_fragment)

    return fragments


def concatenate_audio_files(audio_paths: List[str], output_path: str, ffmpeg_base_url: str) -> Optional[str]:
    """Concatena múltiples archivos de audio en uno solo usando ffmpeg-api."""
    if not audio_paths:
        return None

    if len(audio_paths) == 1:
        import shutil
        shutil.copy(audio_paths[0], output_path)
        return output_path

    try:
        concat_endpoint = f"{ffmpeg_base_url.rstrip('/')}/audio/concatenate"

        payload = {
            "paths": audio_paths,
            "output_format": "mp3"
        }

        logger.info(f"[TTS] Llamando a ffmpeg-api para concatenar {len(audio_paths)} archivos...")
        resp = requests.post(concat_endpoint, json=payload, timeout=300)

        if resp.status_code != 200:
            logger.error(f"[TTS] Error HTTP en concatenación ({resp.status_code}): {resp.text[:200]}")
            return None

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(resp.content)

        logger.info(f"[TTS] ✅ Audio concatenado: {output_path}")
        return output_path

    except requests.exceptions.Timeout:
        logger.error("[TTS] Timeout en concatenación (300s)")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[TTS] No se pudo conectar al servicio de concatenación: {e}")
        return None
    except Exception as e:
        logger.error(f"[TTS] Error en concatenación: {e}")
        return None


class TTSFromArticleUseCase:
    """Caso de uso para generar audio TTS desde artículos."""

    def __init__(self, tts_adapter: TTSPort, audio_converter: AudioConverterPort):
        self._tts = tts_adapter
        self._converter = audio_converter

    def execute(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Genera audio TTS para un artículo, dividiendo en fragmentos si es necesario."""
        if not self._tts.is_available():
            logger.warning("[TTS] Servicio TTS no disponible, saltando generación de audio")
            return article

        content = article.get("content", "")
        if not content:
            logger.warning("[TTS] Artículo sin contenido, saltando generación de audio")
            return article

        cleaned_content = TTSTextProcessor.process(content)
        if not cleaned_content:
            logger.warning("[TTS] Contenido vacío después de limpieza, saltando generación de audio")
            return article

        try:
            fragments = split_text_by_sentences(cleaned_content, COQUI_TTS_CHAR_LIMIT)

            if len(fragments) > 1:
                logger.info(
                    f"[TTS] Contenido dividido en {len(fragments)} fragmentos "
                    f"(límite Coqui para español: {COQUI_TTS_CHAR_LIMIT} chars)"
                )

            audio_paths = []
            for i, fragment in enumerate(fragments, 1):
                logger.debug(f"[TTS] Generando fragmento {i}/{len(fragments)} ({len(fragment)} chars)")
                fragment_audio = self._tts.text_to_speech(text=fragment)
                if fragment_audio:
                    audio_paths.append(fragment_audio)
                else:
                    logger.warning(f"[TTS] No se generó audio para fragmento {i}")

            if not audio_paths:
                logger.warning("[TTS] No se generó audio para ningún fragmento")
                return article

            if len(audio_paths) > 1:
                import uuid
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                output_file = f"/tmp/audios/concatenated_{timestamp}_{uuid.uuid4().hex[:8]}.mp3"
                Path(output_file).parent.mkdir(parents=True, exist_ok=True)

                from src.shared.adapters.audio_converter_factory import get_audio_converter_url
                audio_path = concatenate_audio_files(audio_paths, output_file, get_audio_converter_url())

                for frag_path in audio_paths:
                    try:
                        Path(frag_path).unlink(missing_ok=True)
                    except Exception as e:
                        logger.debug(f"[TTS] Error limpiando fragmento: {e}")
            else:
                audio_path = audio_paths[0]

            if not audio_path:
                logger.warning("[TTS] No se generó audio final")
                return article

            audio_ext = Path(audio_path).suffix.lower()
            if audio_ext == ".wav":
                logger.info("[TTS] Convirtiendo WAV a MP3 (64k) para reducir tamaño...")
                mp3_path = self._converter.convert_to_mp3(
                    input_path=audio_path,
                    bitrate="64k",
                    delete_original=True,
                )
                if mp3_path and Path(mp3_path).exists():
                    article["tts_audio_path"] = mp3_path
                    logger.info(f"[TTS] Audio convertido a MP3: {mp3_path} ({Path(mp3_path).stat().st_size / 1024 / 1024:.1f} MB)")
                else:
                    article["tts_audio_path"] = audio_path
                    logger.warning("[TTS] No se pudo convertir WAV a MP3, usando WAV original")
            else:
                article["tts_audio_path"] = audio_path
                logger.info(f"[TTS] Audio generado: {audio_path}")

        except Exception as e:
            logger.warning(f"[TTS] Error al generar audio (no bloquea pipeline): {e}")

        return article

    def execute_batch(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Genera audio TTS para una lista de artículos."""
        if not self._tts.is_available():
            logger.warning("[TTS] Servicio TTS no disponible, saltando generación de audio")
            return articles
        return [self.execute(article) for article in articles]


def run_tts_from_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """Función de conveniencia para generar audio TTS desde un artículo."""
    from src.shared.infrastructure.composition_root import create_tts_adapter, create_audio_converter
    use_case = TTSFromArticleUseCase(create_tts_adapter(), create_audio_converter())
    return use_case.execute(article)


def run_tts_from_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Función de conveniencia para generar audio TTS desde una lista de artículos."""
    from src.shared.infrastructure.composition_root import create_tts_adapter, create_audio_converter
    use_case = TTSFromArticleUseCase(create_tts_adapter(), create_audio_converter())
    return use_case.execute_batch(articles)
