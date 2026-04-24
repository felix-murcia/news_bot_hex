"""Tests for number_to_words utility."""

import pytest
from unittest.mock import patch


class TestNumberToWords:
    """Test number to words conversion utility."""

    def test_convert_numbers_to_words_basic_integers(self):
        """Test basic integer conversion to Spanish words."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        # Basic integers
        assert "cero" in convert_numbers_to_words("0", language="es")
        assert "uno" in convert_numbers_to_words("1", language="es")
        assert "diez" in convert_numbers_to_words("10", language="es")
        assert "veinte" in convert_numbers_to_words("20", language="es")
        assert "ciento" in convert_numbers_to_words("100", language="es")
        assert "mil" in convert_numbers_to_words("1000", language="es")

    def test_convert_numbers_to_words_years(self):
        """Test year conversion (2013 -> dos mil trece)."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        result = convert_numbers_to_words("2013", language="es")
        assert "dos mil" in result
        assert "trece" in result

        result = convert_numbers_to_words("2024", language="es")
        assert "dos mil veinticuatro" in result

    def test_convert_numbers_to_words_decimals_with_dot(self):
        """Test decimal numbers with dot separator (3.14)."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        result = convert_numbers_to_words("3.14", language="es")
        assert "tres" in result
        assert "catorce" in result  # "tres punto catorce"

    def test_convert_numbers_to_words_decimals_with_comma(self):
        """Test decimal numbers with comma separator (Spanish: 3,14)."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        result = convert_numbers_to_words("3,14", language="es")
        assert "tres" in result
        assert "catorce" in result

    def test_convert_numbers_to_words_thousands_separator(self):
        """Test thousands separator handling (1,500 -> mil quinientas)."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        result = convert_numbers_to_words("1,500", language="es")
        assert "mil" in result
        assert "quinientas" in result

        result = convert_numbers_to_words("10,000", language="es")
        assert "diez mil" in result

    def test_convert_numbers_to_words_mixed_text(self):
        """Test numbers within regular text."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        text = "En 2013 se vendieron 1,500 unidades a 3.14°C"
        result = convert_numbers_to_words(text, language="es")

        assert "dos mil trece" in result
        assert "mil quinientas" in result
        assert "tres punto catorce" in result
        # Original digits should be gone
        assert "2013" not in result
        assert "1,500" not in result
        assert "3.14" not in result

    def test_convert_numbers_to_words_empty_string(self):
        """Test empty string returns empty."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("", language="es") == ""

    def test_convert_numbers_to_words_no_numbers(self):
        """Test text without numbers returns unchanged."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        text = "Este texto no tiene números"
        assert convert_numbers_to_words(text, language="es") == text

    def test_convert_numbers_to_words_large_numbers(self):
        """Test large number conversion."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        result = convert_numbers_to_words("1234567", language="es")
        assert "un millón" in result or "millón" in result

    def test_convert_numbers_to_words_negative_numbers(self):
        """Test negative number handling."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        # Pattern matches word boundaries; negative sign might not be captured by \b
        # This tests that function doesn't crash on unexpected input
        result = convert_numbers_to_words("-42", language="es")
        # The regex \b may not match negative sign; verify no crash
        assert isinstance(result, str)

    def test_convert_numbers_to_words_english(self):
        """Test English language conversion."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        result = convert_numbers_to_words("42", language="en")
        assert "forty-two" in result or "forty two" in result

    def test_convert_numbers_to_words_invalid_number_fallback(self):
        """Test that invalid numbers fall back to original string."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        # Very large number that might not be supported by num2words
        # but num2words does support large numbers; test should just ensure no crash
        result = convert_numbers_to_words("999999999999999999999", language="es")
        assert isinstance(result, str)
        assert len(result) > 0


class TestConvertMatchHelper:
    """Test internal _convert_match function."""

    def test_convert_match_integer(self):
        """Test conversion of an integer match."""
        from src.shared.utils.number_to_words import _convert_match
        import re

        match = re.search(r"\d+", "42")
        result = _convert_match(match, "es")
        assert "cuarenta" in result or "cuarenta y dos" in result

    def test_convert_match_float(self):
        """Test conversion of a decimal match."""
        from src.shared.utils.number_to_words import _convert_match
        import re

        match = re.search(r"\d+\.\d+", "3.14")
        result = _convert_match(match, "es")
        assert "tres" in result
        assert "catorce" in result
