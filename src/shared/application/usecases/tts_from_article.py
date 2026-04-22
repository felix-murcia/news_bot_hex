"""Use case para generar audio TTS desde artículos."""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.logging_config import get_logger
from src.shared.adapters.tts_adapter import text_to_speech, is_tts_available
from src.shared.adapters.audio_converter import AudioConverter

logger = get_logger("shared.usecases.tts")

# Instancia global del conversor de audio
_audio_converter = AudioConverter()


def clean_text_for_tts(text: str) -> str:
    """Limpia texto eliminando HTML, scripts, estilos y caracteres no deseados para TTS.

    Args:
        text: Texto crudo del artículo (puede contener HTML).

    Returns:
        Texto limpio listo para síntesis de voz.
    """
    if not text:
        return ""

    # Eliminar scripts y estilos
    text = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<h[12].*?</h[12]>", "\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<strong.*?</strong>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"Washington", "Wáshington", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(
        r"Silicon Valley", "Sílicon Valey", text, flags=re.DOTALL | re.IGNORECASE
    )

    # Eliminar todas las etiquetas HTML restantes
    text = re.sub(r"<[^>]+>", "", text)

    # Decodificar entidades HTML comunes
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "y")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")

    # Normalizar saltos de línea
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Eliminar URLs
    text = re.sub(r"https?://\S+", "", text)

    # Eliminar menciones de redes sociales (@usuario)
    text = re.sub(r"@\w+", "", text)

    # Eliminar hashtags (opcional para TTS)
    text = re.sub(r"#\w+", "", text)

    # Eliminar líneas demasiado cortas (restos de UI)
    lines = text.splitlines()
    lines = [line for line in lines if len(line.strip()) > 3]

    text = "\n".join(lines).strip()

    # Colapsar espacios múltiples
    text = re.sub(r" {2,}", " ", text)

    return text.strip()


class TTSFromArticleUseCase:
    """Caso de uso para generar audio TTS desde artículos."""

    def __init__(self):
        """Inicializa el use case. No requiere configuración TTS,
        el adaptador usa sus propios defaults facilitados por la fábrica."""
        pass

    def execute(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Genera audio TTS para un artículo."""
        if not is_tts_available():
            logger.warning(
                "[TTS] Servicio TTS no disponible, saltando generación de audio"
            )
            return article

        content = article.get("content", "")
        if not content:
            logger.warning("[TTS] Artículo sin contenido, saltando generación de audio")
            return article

        cleaned_content = clean_text_for_tts(content)
        if not cleaned_content:
            logger.warning(
                "[TTS] Contenido vacío después de limpieza, saltando generación de audio"
            )
            return article

        try:
            # El adaptador seleccionado por TTS_MODE usará su configuración propia
            audio_path = text_to_speech(text=cleaned_content)
            if not audio_path:
                logger.warning("[TTS] No se generó audio (ruta vacía)")
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
