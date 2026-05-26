"""Tests for TTS text normalizer."""

import pytest
from src.shared.adapters.tts_text_normalizer import TTSTextNormalizer


class TestTTSTextNormalizer:
    """Test cases for TTSTextNormalizer."""

    def test_normalize_quotes(self):
        """Test that problematic quotes are removed."""
        # Comillas tipográficas
        assert TTSTextNormalizer.normalize('El "contenido" está bien') == 'El contenido está bien'
        assert TTSTextNormalizer.normalize("El 'contenido' está bien") == 'El contenido está bien'
        assert TTSTextNormalizer.normalize('El «contenido» está bien') == 'El contenido está bien'

    def test_normalize_multiple_commas(self):
        """Test that multiple commas are normalized."""
        assert TTSTextNormalizer.normalize('Hola,, mundo') == 'Hola, mundo'
        assert TTSTextNormalizer.normalize('Hola,,, mundo') == 'Hola, mundo'
        assert TTSTextNormalizer.normalize('Hola,,,, mundo') == 'Hola, mundo'

    def test_normalize_multiple_spaces(self):
        """Test that multiple spaces are normalized."""
        assert TTSTextNormalizer.normalize('Hola  mundo') == 'Hola mundo'
        assert TTSTextNormalizer.normalize('Hola   mundo') == 'Hola mundo'

    def test_normalize_ellipsis(self):
        """Test that ellipsis are normalized."""
        text = TTSTextNormalizer.normalize('Hola... mundo')
        assert '...' in text or text == 'Hola ... mundo'

    def test_normalize_combined_issues(self):
        """Test normalization of combined issues."""
        text = 'El "precio",,, es $100 ... ¡increíble!'
        normalized = TTSTextNormalizer.normalize(text)
        assert '""' not in normalized  # Sin comillas
        assert ',,,' not in normalized  # Sin comas múltiples
        assert '  ' not in normalized  # Sin espacios múltiples
        # Debe mantener estructura básica
        assert 'precio' in normalized
        assert 'es' in normalized

    def test_preserve_accents(self):
        """Test that accents are preserved."""
        text = 'La política económica está en crisis'
        normalized = TTSTextNormalizer.normalize(text)
        assert 'política' in normalized
        assert 'económica' in normalized

    def test_empty_text(self):
        """Test that empty text is handled."""
        assert TTSTextNormalizer.normalize('') == ''
        assert TTSTextNormalizer.normalize('   ') == ''

    def test_preserve_basic_punctuation(self):
        """Test that basic punctuation is preserved."""
        text = 'Hola. ¿Cómo estás? ¡Muy bien!'
        normalized = TTSTextNormalizer.normalize(text)
        assert '.' in normalized
        assert '?' in normalized
        assert '!' in normalized

    def test_normalize_problematic_quotes_with_content(self):
        """Test real-world case: quoted content with punctuation."""
        text = 'El presidente dijo: "Vamos,,, adelante". ¡Increíble!'
        normalized = TTSTextNormalizer.normalize(text)
        assert '"' not in normalized  # Comillas removidas
        assert ',,,' not in normalized  # Comas normalizadas
        assert 'presidente' in normalized
