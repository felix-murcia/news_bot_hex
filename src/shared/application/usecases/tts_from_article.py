"""Use case para generar audio TTS desde artículos."""

import re
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.logging_config import get_logger
from config.settings import Settings
from src.shared.adapters.tts_adapter import text_to_speech, is_tts_available
from src.shared.adapters.audio_converter_factory import get_audio_converter
from src.shared.adapters.tts_text_processor import TTSTextProcessor

logger = get_logger("shared.usecases.tts")

# Instancia global del conversor de audio
_audio_converter = get_audio_converter()

# Límite de caracteres para Coqui TTS en español
COQUI_TTS_CHAR_LIMIT = 239


def split_text_by_sentences(text: str, char_limit: int = COQUI_TTS_CHAR_LIMIT) -> List[str]:
    """Divide el texto en fragmentos respetando el límite de caracteres y oraciones.

    Intenta mantener las oraciones completas dentro del límite.

    Args:
        text: Texto a dividir
        char_limit: Límite de caracteres por fragmento

    Returns:
        Lista de fragmentos de texto
    """
    if len(text) <= char_limit:
        return [text]

    # Dividir por oraciones manteniendo los puntos
    # Patrones: . ! ? seguidos de espacio o fin de texto
    sentences = re.split(r'(?<=[.!?])\s+', text)

    fragments = []
    current_fragment = ""

    for sentence in sentences:
        # Si una oración sola supera el límite, dividir por comas
        if len(sentence) > char_limit:
            if current_fragment:
                fragments.append(current_fragment)
                current_fragment = ""

            # Dividir la oración larga por comas
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
            # Intentar agregar la oración al fragmento actual
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


def concatenate_audio_files(audio_paths: List[str], output_path: str) -> Optional[str]:
    """Concatena múltiples archivos de audio en uno solo usando ffmpeg-api.

    Args:
        audio_paths: Lista de rutas de archivos de audio
        output_path: Ruta del archivo de salida

    Returns:
        Ruta del archivo concatenado o None si falla
    """
    if not audio_paths:
        return None

    if len(audio_paths) == 1:
        # Si solo hay un archivo, copiarlo al destino
        import shutil
        shutil.copy(audio_paths[0], output_path)
        return output_path

    try:
        # Call ffmpeg-api concatenate endpoint
        base_url = Settings.FFMPEG_API_URL.rstrip("/")
        concat_endpoint = f"{base_url}/audio/concatenate"

        payload = {
            "paths": audio_paths,
            "output_format": "mp3"
        }

        logger.info(f"[TTS] Llamando a ffmpeg-api para concatenar {len(audio_paths)} archivos...")
        resp = requests.post(concat_endpoint, json=payload, timeout=300)

        if resp.status_code != 200:
            logger.error(
                f"[TTS] Error HTTP en concatenación ({resp.status_code}): {resp.text[:200]}"
            )
            return None

        # Response is binary audio data
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

    def __init__(self):
        """Inicializa el use case. No requiere configuración TTS,
        el adaptador usa sus propios defaults facilitados por la fábrica."""
        pass

    def execute(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Genera audio TTS para un artículo, dividiendo en fragmentos si es necesario."""
        if not is_tts_available():
            logger.warning(
                "[TTS] Servicio TTS no disponible, saltando generación de audio"
            )
            return article

        content = article.get("content", "")
        if not content:
            logger.warning("[TTS] Artículo sin contenido, saltando generación de audio")
            return article

        cleaned_content = TTSTextProcessor.process(content)
        if not cleaned_content:
            logger.warning(
                "[TTS] Contenido vacío después de limpieza, saltando generación de audio"
            )
            return article

        try:
            # Dividir el contenido en fragmentos si supera el límite
            fragments = split_text_by_sentences(cleaned_content, COQUI_TTS_CHAR_LIMIT)

            if len(fragments) > 1:
                logger.info(
                    f"[TTS] Contenido dividido en {len(fragments)} fragmentos "
                    f"(límite Coqui para español: {COQUI_TTS_CHAR_LIMIT} chars)"
                )

            audio_paths = []
            for i, fragment in enumerate(fragments, 1):
                logger.debug(f"[TTS] Generando fragmento {i}/{len(fragments)} ({len(fragment)} chars)")
                fragment_audio = text_to_speech(text=fragment)
                if fragment_audio:
                    audio_paths.append(fragment_audio)
                else:
                    logger.warning(f"[TTS] No se generó audio para fragmento {i}")

            if not audio_paths:
                logger.warning("[TTS] No se generó audio para ningún fragmento")
                return article

            # Si hay múltiples fragmentos, concatenarlos
            if len(audio_paths) > 1:
                # Generar ruta de salida para audio concatenado
                import uuid
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                output_file = f"/tmp/audios/concatenated_{timestamp}_{uuid.uuid4().hex[:8]}.mp3"
                Path(output_file).parent.mkdir(parents=True, exist_ok=True)

                audio_path = concatenate_audio_files(audio_paths, output_file)

                # Limpiar archivos temporales de fragmentos
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

            # Asegurar que el audio esté en MP3 (convertir si es WAV)
            audio_ext = Path(audio_path).suffix.lower()
            if audio_ext == ".wav":
                logger.info("[TTS] Convirtiendo WAV a MP3 (64k) para reducir tamaño...")
                mp3_path = _audio_converter.convert_to_mp3(
                    input_path=audio_path,
                    bitrate="64k",
                    delete_original=True,  # Eliminar WAV tras conversión
                )
                if mp3_path and Path(mp3_path).exists():
                    article["tts_audio_path"] = mp3_path
                    logger.info(
                        f"[TTS] Audio convertido a MP3: {mp3_path} ({Path(mp3_path).stat().st_size / 1024 / 1024:.1f} MB)"
                    )
                else:
                    # Si la conversión falla, mantener WAV (aunque ocupará más)
                    article["tts_audio_path"] = audio_path
                    logger.warning(
                        "[TTS] No se pudo convertir WAV a MP3, usando WAV original"
                    )
            else:
                article["tts_audio_path"] = audio_path
                logger.info(f"[TTS] Audio generado: {audio_path}")

        except Exception as e:
            logger.warning(f"[TTS] Error al generar audio (no bloquea pipeline): {e}")

        return article

    def execute_batch(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Genera audio TTS para una lista de artículos.

        Args:
            articles: Lista de diccionarios con datos de artículos.

        Returns:
            Lista de artículos actualizados con 'tts_audio_path'.
        """
        if not is_tts_available():
            logger.warning(
                "[TTS] Servicio TTS no disponible, saltando generación de audio"
            )
            return articles

        return [self.execute(article) for article in articles]


def run_tts_from_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """Función de conveniencia para generar audio TTS desde un artículo."""
    use_case = TTSFromArticleUseCase()
    return use_case.execute(article)


def run_tts_from_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Función de conveniencia para generar audio TTS desde una lista de artículos."""
    use_case = TTSFromArticleUseCase()
    return use_case.execute_batch(articles)
