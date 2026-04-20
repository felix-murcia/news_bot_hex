"""Use case para generar audio TTS desde artículos."""

import re
from typing import Dict, Any, List, Optional

from config.logging_config import get_logger
from src.shared.adapters.tts_adapter import text_to_speech, is_tts_available

logger = get_logger("shared.usecases.tts")


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

    def __init__(
        self,
        voice: Optional[str] = None,
        model: Optional[str] = None,
    ):
        from config.settings import Settings

        self.voice = voice or Settings.TTS_VOICE
        self.model = model or Settings.TTS_MODEL

    def execute(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Genera audio TTS para un artículo.

        Args:
            article: Diccionario con los datos del artículo (debe contener 'content').

        Returns:
            Diccionario con el artículo actualizado incluyendo 'tts_audio_path'.
        """
        if not is_tts_available():
            logger.warning(
                "[TTS] Servicio TTS no disponible, saltando generación de audio"
            )
            return article

        content = article.get("content", "")
        if not content:
            logger.warning("[TTS] Artículo sin contenido, saltando generación de audio")
            return article

        # Limpiar HTML y caracteres no deseados
        cleaned_content = clean_text_for_tts(content)
        if not cleaned_content:
            logger.warning(
                "[TTS] Contenido vacío después de limpieza, saltando generación de audio"
            )
            return article

        try:
            audio_path = text_to_speech(
                text=cleaned_content,
                voice=self.voice,
                model=self.model,
            )
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
