"""Text preprocessing for TTS services to avoid synthesis artifacts."""

import re
from typing import Optional


class TTSTextNormalizer:
    """Normaliza texto para TTS, evitando artefactos de síntesis."""

    @staticmethod
    def normalize(text: str) -> str:
        """
        Normaliza texto para mejorar síntesis de Coqui TTS.

        Problemas evitados:
        - Comillas simples/dobles que causan bloqueos
        - Múltiples comas seguidas que generan sonidos raros
        - Espacios múltiples
        - Caracteres especiales problemáticos

        Args:
            text: Texto original

        Returns:
            Texto normalizado apto para TTS
        """
        if not text or not text.strip():
            return ""

        # 1. Reemplazar comillas tipográficas y problemáticas con espacios
        # Elimina: "" '' « » „ ‟
        text = re.sub(r'[""''«»„‟]', ' ', text)
        # Reemplazar comillas normales con nada (para citas breves)
        text = re.sub(r'["\']', ' ', text)

        # 2. Normalizar múltiples comas seguidas a una sola
        # Convierte: ,,,, o ,,, a ,
        text = re.sub(r',{2,}', ',', text)

        # 3. Normalizar múltiples espacios a uno solo
        text = re.sub(r' {2,}', ' ', text)

        # 4. Reemplazar guiones problemáticos
        # Mantener guiones normales (-) pero normalizar otros
        text = re.sub(r'[–—]', '-', text)

        # 5. Normalizar puntos suspensivos
        # ... o … a una pausa (espacio)
        text = re.sub(r'\.{3,}|…', ' ... ', text)

        # 6. Remover caracteres especiales problemáticos para TTS
        # Mantener: letras, números, puntuación básica, acentos
        # Remover: símbolos raros, caracteres de control
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;\(\)áéíóúñ¿¡]', ' ', text, flags=re.UNICODE)

        # 7. Normalizar espacios alrededor de puntuación
        # Espacios antes de puntuación final
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        # Espacio después de puntuación (excepto dentro de puntos suspensivos)
        text = re.sub(r'([.,!?;:])\s*', r'\1 ', text)
        text = re.sub(r'\.\s+\.', '...', text)  # Restaurar puntos suspensivos

        # 8. Remover espacios múltiples nuevamente (después de normalizaciones)
        text = re.sub(r' {2,}', ' ', text)

        # 9. Limpiar inicio y fin
        text = text.strip()

        return text
