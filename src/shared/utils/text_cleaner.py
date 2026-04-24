"""Text cleaning utilities for TTS processing.

Provides functions to sanitize and normalize text content
before sending it to Text-to-Speech engines.
"""

import re

from src.shared.utils.number_to_words import convert_numbers_to_words


def clean_text_for_tts(text: str, convert_numbers: bool = True, language: str = "es") -> str:
    """Limpia texto eliminando HTML, scripts, estilos y caracteres no deseados para TTS.

    Aplica una serie de transformaciones para hacer el texto compatible
    con motores de síntesis de voz, especialmente Coqui TTS que no maneja
    bien ciertos caracteres especiales y números.

    Args:
        text: Texto crudo del artículo (puede contener HTML).
        convert_numbers: Si es True, convierte dígitos numéricos a palabras.
                        Default True para uso con Coqui TTS.
        language: Idioma para la conversión de números (default: 'es').

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

    # Correcciones de pronunciación problemáticas
    text = re.sub(r"Washington", "Wáshington", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"Silicon Valley", "Sílicon Valey", text, flags=re.DOTALL | re.IGNORECASE)

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

    # Convertir caracteres numéricos a palabras (requerido para Coqui TTS)
    if convert_numbers:
        text = convert_numbers_to_words(text, language=language)

    return text.strip()
