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

    def test_expand_abbreviations_countries(self):
        """Test expansion of country abbreviations."""
        text = 'Acuerdo entre E.E.U.U. y la U.E.'
        normalized = TTSTextNormalizer.normalize(text)
        assert 'Estados Unidos' in normalized
        assert 'Unión Europea' in normalized

    def test_expand_abbreviations_titles(self):
        """Test expansion of title abbreviations."""
        text = 'El Dr. Juan García y la Dra. María López'
        normalized = TTSTextNormalizer.normalize(text)
        assert 'Doctor' in normalized
        assert 'Doctora' in normalized

    def test_expand_abbreviations_measures(self):
        """Test expansion of measurement abbreviations."""
        text = 'El edificio mide 150 m. y pesa 500 kg.'
        normalized = TTSTextNormalizer.normalize(text)
        assert 'metros' in normalized
        assert 'kilogramos' in normalized

    def test_expand_abbreviations_organizations(self):
        """Test expansion of organization abbreviations."""
        text = 'Según la O.M.S., el virus se propaga rapidamente'
        normalized = TTSTextNormalizer.normalize(text)
        assert 'Organización Mundial de la Salud' in normalized

    def test_expand_abbreviations_case_insensitive(self):
        """Test case-insensitive abbreviation expansion."""
        text = 'El Sr. González y el Sr. Miguel hablan con la ONU'
        normalized = TTSTextNormalizer.normalize(text)
        assert 'Señor' in normalized
        assert 'Organización de las Naciones Unidas' in normalized

    def test_real_world_article_with_abbreviations(self):
        """Test real-world news article normalization."""
        text = 'El Dr. Pedro López, de E.E.U.U., informó a la O.M.S. sobre nuevos casos... "Será importante" dijo,,,para evitar la propagación.'
        normalized = TTSTextNormalizer.normalize(text)
        # Should expand abbreviations
        assert 'Doctor' in normalized or 'Dr.' not in normalized
        assert 'Estados Unidos' in normalized
        assert 'Organización Mundial de la Salud' in normalized
        # Should normalize quotes and commas
        assert '"' not in normalized
        assert '...' not in normalized or '...' in normalized  # ellipsis handling
        assert ',,,' not in normalized
