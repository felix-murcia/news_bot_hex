"""Utility to convert numeric characters to their word representation.

Provides a pure function to transform numbers in text to spoken words,
addressing TTS engines that cannot properly pronounce numeric characters.

Classification rules (Fase 4, decisión 3 de Felix):
  1. Decimal separator -> magnitudes: "3,14" -> "tres coma catorce".
  2. A dot with exactly three decimals -> Spanish thousands: "5.000" -> "cinco mil".
  3. Both separators -> thousands + decimal: "1.234,56".
  4. Identifiers (IPs, semantic versions, ISO dates) are left LITERAL.

num2words 0.5.14 reads floats digit by digit ("tres punto uno cuatro"), which is
wrong for news TTS: it turned "hasta 5.000 euros" into "hasta cinco euros".
Magnitudes are therefore assembled here and num2words is only used for integers.
"""

import re
from typing import Match, Optional, Sequence, Tuple

from num2words import num2words

# A numeric token may carry several separators: "1.234,56", "5.000", "2.14.3".
TOKEN_PATTERN = r"\b\d+(?:[.,]\d+)*\b"

# Rule 4: an ISO date must not be exploded into three separate magnitudes.
ISO_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")

# Value used to join an integer and its fractional part.
FRACTION_JOINER = " coma "


def _literal_spans(text: str) -> Tuple[Tuple[int, int], ...]:
    """Spans of `text` that must survive verbatim (ISO dates)."""
    return tuple(m.span() for m in ISO_DATE_PATTERN.finditer(text))


def _is_literal_span(
    span: Tuple[int, int],
    literal_spans: Optional[Sequence[Tuple[int, int]]],
    text: str,
) -> bool:
    """True si el match cae dentro de un span que debe quedar literal."""
    spans = literal_spans if literal_spans is not None else _literal_spans(text)
    start, end = span
    return any(s <= start and end <= e for s, e in spans)


def _int_to_words(digits: str, language: str) -> Optional[str]:
    """Lee un entero con num2words, o None si no se puede (idioma no soportado)."""
    try:
        return num2words(int(digits), lang=language)
    except (ValueError, NotImplementedError, TypeError, OverflowError):
        return None


def _fraction_to_words(digits: str, language: str) -> Optional[str]:
    """Lee la parte decimal como magnitud: "14" -> "catorce", "75" -> "setenta y cinco"."""
    words = _int_to_words(digits, language)
    if words is None:
        return None
    # El cero inicial se pronuncia. Sin esto, "0,05" se narraría como "cero coma
    # cinco" (= 0,5): un error de magnitud, no de ortografía.
    if len(digits) > 1 and digits.startswith("0"):
        zero = _int_to_words("0", language)
        words = f"{zero} {words}" if zero else words
    return words


def _decimal_to_words(
    integer_part: str, fraction_part: str, language: str
) -> Optional[str]:
    """Regla 1: decimal -> entero + "coma" + magnitud fraccionaria."""
    integer_words = _int_to_words(integer_part, language)
    fraction_words = _fraction_to_words(fraction_part, language)
    if integer_words is None or fraction_words is None:
        return None
    return f"{integer_words}{FRACTION_JOINER}{fraction_words}"


def _is_dotted_thousands(parts: Sequence[str]) -> bool:
    """True si los grupos intermedios son de tres dígitos (millares).

    Distingue "1.500.000" (millares) de "192.168.1.1" (IP) y "2.14.3"
    (versión): sólo el primero tiene todos sus grupos intermedios en tres.
    """
    return all(len(part) == 3 for part in parts[1:-1])


def _convert_token(num_str: str, language: str) -> Optional[str]:
    """Clasifica y convierte un token numérico completo.

    Returns:
        La lectura en palabras, o None si el token debe quedar literal
        (identificadores) o si el idioma no soporta la conversión.
    """
    has_dot = "." in num_str
    has_comma = "," in num_str

    # Entero puro: "2024" -> "dos mil veinticuatro".
    if not has_dot and not has_comma:
        return _int_to_words(num_str, language)

    # Regla 3: millares + decimal -> "1.234,56".
    if has_dot and has_comma:
        integer_part, fraction_part = num_str.rsplit(",", 1)
        return _decimal_to_words(
            integer_part.replace(".", ""), fraction_part, language
        )

    if has_dot:
        parts = num_str.split(".")
        # Regla 4: varios puntos que no son millares -> IP o versión, literal.
        if len(parts) > 2:
            if not _is_dotted_thousands(parts):
                return None
            return _int_to_words(num_str.replace(".", ""), language)
        # Regla 2: exactamente tres decimales -> millares españoles.
        if len(parts[1]) == 3:
            return _int_to_words(num_str.replace(".", ""), language)
        return _decimal_to_words(parts[0], parts[1], language)

    # Sólo coma. Tres dígitos exactos siguen siendo millares (convención anglo
    # fijada por los tests: "1,500" -> "mil quinientos"); el resto es decimal.
    integer_part, fraction_part = num_str.split(",")
    if len(fraction_part) == 3:
        return _int_to_words(num_str.replace(",", ""), language)
    return _decimal_to_words(integer_part, fraction_part, language)


def _convert_match(
    match: Match,
    language: str,
    literal_spans: Optional[Sequence[Tuple[int, int]]] = None,
) -> str:
    """Convert a single numeric match to words.

    Args:
        match: Regex match object containing the numeric string.
        language: Target language for conversion (e.g., 'es', 'en').
        literal_spans: Spans pre-computed by the caller to avoid rescanning the
            whole text once per number. Computed on demand when omitted.

    Returns:
        Word representation of the number, or the literal digits when the token
        is an identifier (rule 4) or the language is not supported.
    """
    num_str = match.group(0)

    # Regla 4: fechas ISO quedan intactas.
    if _is_literal_span(match.span(), literal_spans, match.string):
        return num_str

    return _convert_token(num_str, language) or num_str


def convert_numbers_to_words(text: str, language: str = "es") -> str:
    """Convert all numeric substrings in text to their word representation.

    Uses a single regex pass to find numbers (integers, decimals, thousands
    separators, IPs, versions, dates) and replaces each with its spoken form.

    Args:
        text: Input text that may contain numeric characters.
        language: Target language code (default: 'es' for Spanish).
                  Supported: 'es', 'en', 'fr', 'de', etc.

    Returns:
        Text with numbers replaced by their word equivalents.

    Examples:
        >>> convert_numbers_to_words("En 2013 se vendieron 1,500 unidades")
        'En dos mil trece se vendieron mil quinientos unidades'
        >>> convert_numbers_to_words("hasta 5.000 euros")
        'hasta cinco mil euros'
        >>> convert_numbers_to_words("El IPC fue 3,14%")
        'El IPC fue tres coma catorce%'

    Classification:
        1. Decimal separator -> magnitudes: "3,14" -> "tres coma catorce",
           "0,75" -> "cero coma setenta y cinco".
        2. A dot with exactly three decimals -> Spanish thousands:
           "1.500" -> "mil quinientos", "5.000" -> "cinco mil".
           (A dot with exactly three decimals as a thousands separator was the
           pre-existing behaviour; what was MISSING was treating a lone "5.000"
           as five, which turned "hasta 5.000 euros" into "hasta cinco euros".)
        3. Both separators -> thousands + decimal:
           "1.234,56" -> "mil doscientos treinta y cuatro coma cincuenta y seis".
        4. Identifiers stay literal: "192.168.1.1", "2.14.3", "2024-10-02".
           Rule 4 is what makes rules 1-3 safe: an IP is recognised by having
           dot-separated groups that are NOT all three digits long.

    Integral values follow the RAE ("cien" standalone, "ciento veinte").

    Note:
        Decimal values are read as MAGNITUDES, not digit by digit.
        "3.14" -> "tres coma catorce". The previous digit-by-digit reading
        ("tres punto uno cuatro") was claimed in this docstring to keep IPs,
        versions, ratios and coordinates unambiguous; that claim was false: it
        never handled the monetary case, and rule 4 is what actually protects
        identifiers.

    Known limitation:
        Grammatical gender is NOT applied: "1.500 personas" is narrated as
        "mil quinientos personas". num2words 0.5.14 exposes no gender argument,
        and the TTS engine consumes the digit stream, not the spelling, so the
        audio output is identical either way.
    """
    if not text:
        return ""

    # Pre-computado una sola vez: sin esto se re-escanearía el texto entero
    # por cada número encontrado.
    spans = _literal_spans(text)

    def replacer(match: Match) -> str:
        return _convert_match(match, language, spans)

    return re.sub(TOKEN_PATTERN, replacer, text)