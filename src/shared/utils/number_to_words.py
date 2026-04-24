"""Utility to convert numeric characters to their word representation.

Provides a pure function to transform numbers in text to spoken words,
addresses TTS engines that cannot properly pronounce numeric characters.
"""

import re
from typing import Match
from num2words import num2words


def _convert_match(match: Match, language: str) -> str:
    """Convert a single numeric match to words.
    
    Args:
        match: Regex match object containing the numeric string.
        language: Target language for conversion (e.g., 'es', 'en').
        
    Returns:
        Word representation of the number.
    """
    num_str = match.group(0)
    
    # Replace comma as thousands separator temporarily for parsing
    # But keep track if it's actually a decimal comma (Spanish style)
    if ',' in num_str and '.' not in num_str:
        # Spanish style: "1,5" means 1.5
        # Check if it looks like a decimal (single comma between digits)
        parts = num_str.split(',')
        if len(parts) == 2 and len(parts[0]) > 0 and len(parts[1]) <= 2:
            # Likely decimal comma
            try:
                return num2words(num_str.replace(',', '.'), lang=language)
            except (ValueError, NotImplementedError):
                return num_str
        else:
            # Thousands separator - remove it
            num_clean = num_str.replace(',', '')
            try:
                return num2words(int(num_clean), lang=language)
            except (ValueError, NotImplementedError):
                return num_str
    else:
        # Standard format (may include decimal point)
        try:
            # Try as float first (handles decimals)
            if '.' in num_str:
                return num2words(float(num_str), lang=language)
            else:
                return num2words(int(num_str), lang=language)
        except (ValueError, NotImplementedError):
            return num_str


def convert_numbers_to_words(text: str, language: str = "es") -> str:
    """Convert all numeric substrings in text to their word representation.

    Uses regex to find numbers (including decimals and comma-separated formats)
    and replaces them with their spoken form using num2words.

    Args:
        text: Input text that may contain numeric characters.
        language: Target language code (default: 'es' for Spanish).
                  Supported: 'es', 'en', 'fr', 'de', etc.

    Returns:
        Text with numbers replaced by their word equivalents.

    Example:
        >>> convert_numbers_to_words("En 2013 se vendieron 1,500 unidades")
        'En dos mil trece se vendieron mil quinientas unidades'
        >>> convert_numbers_to_words("Temperatura: 3.5°C", language="es")
        'Temperatura: tres punto cinco°C'
    """
    if not text:
        return ""
    
    # Regex pattern to match numbers in various formats:
    # - Integers: 123, 1,000, 10.000 (Spanish thousands separator)
    # - Decimals: 3.14, 3,14 (Spanish decimal comma)
    # - Years: 2024, 1999
    # Pattern explanation:
    #   \b          - word boundary
    #   \d+         - one or more digits
    #   (?:         - non-capturing group for decimal/thousands part
    #     [,.]\d+   - comma or dot followed by digits
    #   )?          - optional
    #   \b          - word boundary
    pattern = r'\b\d+(?:[,.]\d+)?\b'
    
    def replacer(match: Match) -> str:
        return _convert_match(match, language)
    
    return re.sub(pattern, replacer, text)
