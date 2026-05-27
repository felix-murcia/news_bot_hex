"""Tests para la división de texto para TTS."""

import pytest
from src.shared.application.usecases.tts_from_article import split_text_by_sentences, COQUI_TTS_CHAR_LIMIT


class TestTextSplitting:
    """Test cases para split_text_by_sentences."""

    def test_short_text_no_split(self):
        """Texto corto no debe ser dividido."""
        text = "Este es un texto corto."
        result = split_text_by_sentences(text)
        assert len(result) == 1
        assert result[0] == text

    def test_long_text_with_sentences(self):
        """Texto largo con múltiples oraciones debe ser dividido."""
        text = "Primera oración muy larga que necesita más palabras para superar el límite. Segunda oración también muy larga con más contenido. Tercera oración que sigue siendo larga. Cuarta oración adicional. Quinta para asegurar que se supera el límite."
        result = split_text_by_sentences(text)
        assert len(result) > 1
        # Cada fragmento debe estar dentro del límite
        for fragment in result:
            assert len(fragment) <= COQUI_TTS_CHAR_LIMIT

    def test_very_long_single_sentence(self):
        """Oración muy larga debe ser dividida por comas."""
        text = "Este es un texto muy largo con una oración que no tiene punto, pero tiene comas, para que pueda ser dividido en fragmentos más pequeños, respetando el límite de caracteres, sin romper la semántica del texto, de manera que cada fragmento pueda ser sintetizado por Coqui TTS sin truncamientos."
        result = split_text_by_sentences(text)
        assert len(result) > 1
        for fragment in result:
            assert len(fragment) <= COQUI_TTS_CHAR_LIMIT

    def test_respects_char_limit(self):
        """Todos los fragmentos deben respetar el límite de caracteres."""
        text = "Según el jefe de la delegación militar de Estonia, las nuevas directrices de defensa están siendo implementadas. El comunicado oficial fue distribuido a todos los medios de prensa. Los detalles específicos se revelarán en una conferencia de prensa programada para mañana a las 14 horas."
        result = split_text_by_sentences(text)
        for fragment in result:
            assert len(fragment) <= COQUI_TTS_CHAR_LIMIT, f"Fragment too long: {len(fragment)} > {COQUI_TTS_CHAR_LIMIT}: {fragment}"

    def test_preserves_content(self):
        """La división no debe perder contenido."""
        text = "Primera. Segunda. Tercera. Cuarta. Quinta. Sexta."
        result = split_text_by_sentences(text)
        # Recombinar fragmentos
        combined = " ".join(result)
        # Los fragmentos deben contener todas las palabras
        for word in ["Primera", "Segunda", "Tercera", "Cuarta", "Quinta", "Sexta"]:
            assert word in combined

    def test_empty_text(self):
        """Texto vacío debe retornar lista con un elemento vacío."""
        text = ""
        result = split_text_by_sentences(text)
        assert len(result) == 1
        assert result[0] == ""

    def test_text_with_multiple_spaces(self):
        """Texto con espacios múltiples debe ser manejado correctamente."""
        text = "Primera oración.  Segunda oración.   Tercera oración."
        result = split_text_by_sentences(text)
        # No debería fallar y todos deben estar dentro del límite
        for fragment in result:
            assert len(fragment) <= COQUI_TTS_CHAR_LIMIT

    def test_real_world_example(self):
        """Ejemplo del mundo real con texto de noticia."""
        text = "Según el jefe de la delegación militar de Estonia, las nuevas políticas de defensa regional representan un cambio significativo. Las fuerzas armadas del país anunciaron nuevas inversiones en tecnología militar. Los funcionarios expresaron su compromiso con la seguridad de la región."
        result = split_text_by_sentences(text)
        assert len(result) > 0
        for fragment in result:
            assert len(fragment) <= COQUI_TTS_CHAR_LIMIT
            assert fragment.strip()  # No debe ser solo espacios

    def test_custom_char_limit(self):
        """Debe funcionar con límites de caracteres personalizados."""
        text = "Uno. Dos. Tres. Cuatro. Cinco. Seis. Siete. Ocho."
        result = split_text_by_sentences(text, char_limit=10)
        for fragment in result:
            assert len(fragment) <= 10

    def test_punctuation_variations(self):
        """Debe manejar diferentes tipos de puntuación."""
        text = "Pregunta? ¡Exclamación! Normal. Más texto aquí."
        result = split_text_by_sentences(text)
        assert len(result) > 0
        for fragment in result:
            assert len(fragment) <= COQUI_TTS_CHAR_LIMIT
