"""Tests for number_to_words utility.

The expectations below pin the REAL behaviour of the module, which delegates to
num2words==0.5.14 for the magnitudes.

Three rules matter (Fase 4, decisión 3 de Felix):

1. Integers follow the RAE: 100 -> "cien" (not "ciento"; "ciento" is only used
   before another numeral, as in "ciento veinte").

2. A decimal separator is read AS A MAGNITUDE, not digit by digit:
   3,14 -> "tres coma catorce", 0,75 -> "cero coma setenta y cinco".
   num2words reads floats digit by digit ("tres punto uno cuatro"), which is
   wrong for news money ("cinco mil euros") and for ratios.

3. A dot with exactly three decimals is a THOUSANDS separator (Spanish), not a
   decimal: 5.000 -> "cinco mil", not "cinco". This was a real monetary bug:
   "hasta 5.000 euros" used to be narrated as "hasta cinco euros".

Identifiers are left literal (rule 4): IPs, semantic versions and ISO dates must
not be reinterpreted as magnitudes.
"""

import re

import pytest


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
        # RAE: "cien" standalone; "ciento" only before another numeral
        assert "cien" in convert_numbers_to_words("100", language="es")
        assert "ciento" not in convert_numbers_to_words("100", language="es")
        assert convert_numbers_to_words("120", language="es") == "ciento veinte"
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
        """A dot with two decimals is a decimal separator read as a magnitude."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("3.14", language="es") == "tres coma catorce"

    def test_convert_numbers_to_words_decimals_with_comma(self):
        """A Spanish decimal comma is read as a magnitude, not digit by digit."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("3,14", language="es") == "tres coma catorce"
        assert (
            convert_numbers_to_words("0,75", language="es")
            == "cero coma setenta y cinco"
        )

    def test_convert_numbers_to_words_single_decimal_digit(self):
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("3.5", language="es") == "tres coma cinco"
        assert convert_numbers_to_words("3,5", language="es") == "tres coma cinco"

    def test_decimal_leading_zero_is_spoken(self):
        """0,05 must NOT be narrated as 0,5: that is a magnitude error."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("0,05", language="es") == "cero coma cero cinco"
        assert convert_numbers_to_words("3.05", language="es") == "tres coma cero cinco"

    def test_convert_numbers_to_words_dot_thousands_separator(self):
        """A dot with exactly three decimals is Spanish thousands (5.000 -> cinco mil)."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("5.000", language="es") == "cinco mil"
        assert convert_numbers_to_words("1.500", language="es") == "mil quinientos"

    def test_money_is_not_truncated(self):
        """REGRESIÓN: 'hasta 5.000 euros' must never be narrated as 'cinco euros'."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        result = convert_numbers_to_words("hasta 5.000 euros", language="es")
        assert result == "hasta cinco mil euros"
        assert "cinco euros" not in result

    def test_mixed_thousands_and_decimal(self):
        """1.234,56 -> mil doscientos treinta y cuatro coma cincuenta y seis."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("1.234,56", language="es") == (
            "mil doscientos treinta y cuatro coma cincuenta y seis"
        )

    def test_multiple_dot_thousands(self):
        """1.500.000 -> un millón quinientos mil (groups of three are thousands)."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        result = convert_numbers_to_words("1.500.000", language="es")
        assert "millón" in result
        assert result != "1.500.000"

    def test_ip_address_is_left_literal(self):
        """Rule 4: an IPv4 address is not a magnitude."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("192.168.1.1", language="es") == "192.168.1.1"

    def test_semantic_version_is_left_literal(self):
        """Rule 4: 2.14.3 is a version, not a decimal nor thousands."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("2.14.3", language="es") == "2.14.3"

    def test_iso_date_is_left_literal(self):
        """Rule 4: an ISO date must not be split into three magnitudes."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("2024-10-02", language="es") == "2024-10-02"

    def test_ip_address_inside_text_keeps_context(self):
        """The literal IP must survive while surrounding numbers still convert."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        result = convert_numbers_to_words(
            "El servidor 192.168.1.1 tiene 5.000 usuarios", language="es"
        )
        assert "192.168.1.1" in result
        assert "cinco mil" in result

    def test_percentages(self):
        """40% and 3,14% must be read as magnitudes."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("40%", language="es") == "cuarenta%"
        assert convert_numbers_to_words("3,14%", language="es") == "tres coma catorce%"

    def test_regression_rae_magnitudes(self):
        """Regresión: plain magnitudes keep following the RAE."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("100", language="es") == "cien"
        assert convert_numbers_to_words("1500", language="es") == "mil quinientos"

    def test_convert_numbers_to_words_thousands_separator(self):
        """Anglo thousands separators use masculine form ("mil quinientos unidades")."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        result = convert_numbers_to_words("1,500", language="es")
        assert result == "mil quinientos"

        result = convert_numbers_to_words("10,000", language="es")
        assert "diez mil" in result

    def test_convert_numbers_to_words_comma_with_three_digits_is_thousands(self):
        """Three digits after the comma means thousands, not a decimal."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        assert convert_numbers_to_words("1,500", language="es") == "mil quinientos"
        assert (
            convert_numbers_to_words("12,345", language="es")
            == "doce mil trescientos cuarenta y cinco"
        )

    def test_convert_numbers_to_words_mixed_text(self):
        """Test numbers within regular text."""
        from src.shared.utils.number_to_words import convert_numbers_to_words

        text = "En 2013 se vendieron 1,500 unidades a 3.14°C"
        result = convert_numbers_to_words(text, language="es")

        assert result == (
            "En dos mil trece se vendieron mil quinientos unidades a tres coma catorce°C"
        )
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

        match = re.search(r"\d+", "42")
        result = _convert_match(match, "es")
        assert "cuarenta" in result or "cuarenta y dos" in result

    def test_convert_match_float(self):
        """Floats are read as integer magnitude + 'coma' + fractional magnitude."""
        from src.shared.utils.number_to_words import _convert_match

        match = re.search(r"\d+\.\d+", "3.14")
        result = _convert_match(match, "es")
        assert result == "tres coma catorce"

    def test_convert_match_returns_original_when_lang_unsupported(self):
        """An unsupported language must degrade to the literal digits, not raise."""
        from src.shared.utils.number_to_words import _convert_match

        match = re.search(r"\d+", "42")
        result = _convert_match(match, "zz")
        assert result == "42"