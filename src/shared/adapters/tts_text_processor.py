"""Unified text processor for TTS (Text-to-Speech) synthesis.

Provides comprehensive text normalization and cleaning for Coqui TTS and other
speech synthesis engines. Combines abbreviation expansion, HTML cleaning,
punctuation normalization, and number conversion.
"""

import re
from typing import Optional

from src.shared.adapters.abbreviation_dict import ABBREVIATION_MAP


class TTSTextProcessor:
    """
    Unified text processor for TTS synthesis.

    Handles all text normalization and cleaning needed for high-quality
    speech synthesis with Coqui TTS, including:
    - HTML tag removal
    - Abbreviation expansion
    - Punctuation normalization
    - Character cleaning
    - Number conversion
    """

    @staticmethod
    def process(text: str, convert_numbers: bool = True, language: str = "es") -> str:
        """
        Process text for TTS synthesis (main entry point).

        Applies all normalization phases in the correct order for optimal results.

        Args:
            text: Raw text from article (may contain HTML)
            convert_numbers: Convert numeric digits to words (default True)
            language: Language for number conversion (default 'es')

        Returns:
            Cleaned and normalized text ready for speech synthesis
        """
        if not text or not text.strip():
            return ""

        # Phase 0: Remove URLs/emails/mentions BEFORE HTML cleaning
        # (URLs contain : and / which get modified during normalization)
        text = TTSTextProcessor._final_cleanup(text)

        # Phase 1: HTML and markup cleaning
        text = TTSTextProcessor._clean_html(text)

        # Phase 2: Abbreviation expansion
        text = TTSTextProcessor._expand_abbreviations(text)

        # Phase 3: Normalize punctuation and problematic characters
        text = TTSTextProcessor._normalize_punctuation(text)

        # Phase 4: Number conversion
        if convert_numbers:
            text = TTSTextProcessor._convert_numbers_to_words(text, language)

        # Phase 5: Final whitespace cleanup
        text = re.sub(r' {2,}', ' ', text)

        return text.strip()

    @staticmethod
    def _clean_html(text: str) -> str:
        """
        Remove HTML tags, scripts, styles, and decode entities.

        Args:
            text: Text with potential HTML markup

        Returns:
            Text with HTML removed
        """
        if not text:
            return text

        # Remove scripts and styles (entire blocks)
        text = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

        # Convert heading tags to newlines (preserve structure)
        text = re.sub(r"<h[1-6].*?</h[1-6]>", "\n", text, flags=re.DOTALL | re.IGNORECASE)

        # Remove strong/emphasis tags but keep content
        text = re.sub(r"<strong.*?</strong>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<em.*?</em>", "", text, flags=re.DOTALL | re.IGNORECASE)

        # Remove all remaining HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities
        html_entities = {
            "&nbsp;": " ",
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&#39;": "'",
            "&apos;": "'",
        }
        for entity, replacement in html_entities.items():
            text = text.replace(entity, replacement)

        return text

    @staticmethod
    def _expand_abbreviations(text: str) -> str:
        """
        Expand common Spanish abbreviations to full forms.

        Args:
            text: Text with abbreviations

        Returns:
            Text with abbreviations expanded
        """
        if not text:
            return text

        # Sort by length (longest first) to avoid partial replacements
        sorted_abbrevs = sorted(
            ABBREVIATION_MAP.items(), key=lambda x: len(x[0]), reverse=True
        )

        for abbrev, expansion in sorted_abbrevs:
            # Match abbreviation only if not part of a larger word
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(abbrev) + r"(?![a-zA-Z0-9])"
            text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)

        return text

    @staticmethod
    def _normalize_punctuation(text: str) -> str:
        """
        Normalize problematic punctuation and special characters.

        Fixes issues like multiple commas, problematic quotes, etc.

        Args:
            text: Text with punctuation to normalize

        Returns:
            Text with normalized punctuation
        """
        if not text:
            return text

        # Remove/replace problematic quotes
        # Typographic quotes, curly quotes, etc.
        text = re.sub(r'[""''«»„‟]', ' ', text)
        # Remove straight quotes
        text = re.sub(r'["\']', ' ', text)

        # Normalize multiple consecutive commas to single comma
        text = re.sub(r',{2,}', ',', text)

        # Normalize multiple spaces
        text = re.sub(r' {2,}', ' ', text)

        # Standardize dashes
        text = re.sub(r'[–—]', '-', text)

        # Normalize ellipsis
        text = re.sub(r'\.{3,}|…', ' ... ', text)

        # Remove problematic special characters while preserving accents
        # Keep: letters, numbers, basic punctuation, accents
        text = re.sub(
            r'[^\w\s\.\,\!\?\-\:\;\(\)áéíóúñ¿¡]', ' ', text, flags=re.UNICODE
        )

        # Normalize spacing around punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)  # Remove space before
        text = re.sub(r'([.,!?;:])\s*', r'\1 ', text)  # Add space after
        text = re.sub(r'\.\s+\.', '...', text)  # Fix ellipsis

        return text

    @staticmethod
    def _convert_numbers_to_words(text: str, language: str = "es") -> str:
        """
        Convert numeric digits to words for better TTS pronunciation.

        Args:
            text: Text with numbers
            language: Language code (default 'es' for Spanish)

        Returns:
            Text with numbers converted to words
        """
        try:
            from src.shared.utils.number_to_words import convert_numbers_to_words
            return convert_numbers_to_words(text, language=language)
        except ImportError:
            # Fallback if number_to_words is not available
            return text

    @staticmethod
    def _final_cleanup(text: str) -> str:
        """
        Apply final cleanup passes.

        Removes URLs, social media mentions, normalizes line breaks, etc.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        if not text:
            return text

        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)

        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)

        # Remove social media mentions
        text = re.sub(r'@\w+', '', text)

        # Remove hashtags
        text = re.sub(r'#\w+', '', text)

        # Normalize line breaks
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Remove very short lines (UI artifacts, etc.)
        lines = text.splitlines()
        lines = [line for line in lines if len(line.strip()) > 3]
        text = '\n'.join(lines)

        # Final space normalization
        text = re.sub(r' {2,}', ' ', text)

        return text.strip()

    @staticmethod
    def clean_for_display(text: str) -> str:
        """
        Light cleanup for display purposes (not TTS).

        Removes only the most problematic elements without full normalization.

        Args:
            text: Text to clean

        Returns:
            Lightly cleaned text
        """
        if not text:
            return text

        # Remove HTML tags only
        text = re.sub(r'<[^>]+>', '', text)

        # Basic space cleanup
        text = re.sub(r' {2,}', ' ', text)

        return text.strip()
