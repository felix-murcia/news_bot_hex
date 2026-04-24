"""Tests for text_cleaner utility."""

import pytest
from unittest.mock import patch


class TestTextCleaner:
    """Test text cleaning utility for TTS."""

    def test_clean_text_for_tts_basic(self):
        """Test basic text cleaning."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "  Simple text with   extra   spaces  "
        result = clean_text_for_tts(text)
        assert result == "Simple text with extra spaces"

    def test_clean_text_for_tts_empty_string(self):
        """Test empty string handling."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        assert clean_text_for_tts("") == ""
        assert clean_text_for_tts(None) == ""

    def test_clean_text_for_tts_removes_html_tags(self):
        """Test HTML tag removal."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        html = "<p>Paragraph</p><div>Div content</div>"
        result = clean_text_for_tts(html)
        assert "<" not in result
        assert ">" not in result
        assert "Paragraph" in result
        assert "Div content" in result

    def test_clean_text_for_tts_removes_script_tags(self):
        """Test script and style tag removal."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        html = "<script>alert('xss')</script><p>Safe content</p><style>body{}</style>"
        result = clean_text_for_tts(html)
        assert "alert" not in result
        assert "body{}" not in result
        assert "Safe content" in result

    def test_clean_text_for_tts_removes_urls(self):
        """Test URL removal."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "Check https://example.com and http://test.org for info"
        result = clean_text_for_tts(text)
        assert "https://" not in result
        assert "http://" not in result
        assert "Check" in result
        assert "for info" in result

    def test_clean_text_for_tts_removes_mentions(self):
        """Test @mention removal."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "Thanks @user123 and @another_user!"
        result = clean_text_for_tts(text)
        assert "@user123" not in result
        assert "@another_user" not in result
        assert "Thanks" in result

    def test_clean_text_for_tts_removes_hashtags(self):
        """Test hashtag removal."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "Breaking #news #trending #viral"
        result = clean_text_for_tts(text)
        assert "#news" not in result
        assert "#trending" not in result
        assert "#viral" not in result

    def test_clean_text_for_tts_normalizes_line_breaks(self):
        """Test line break normalization."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "Line1\r\nLine2\r\n\r\n\r\nLine3"
        result = clean_text_for_tts(text)
        assert "\r" not in result
        # Excessive newlines collapsed to max 2
        assert "\n\n\n" not in result

    def test_clean_text_for_tts_removes_short_lines(self):
        """Test removal of very short lines (likely UI remnants)."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "Valid line\nAB\nAnother valid line\nX"
        result = clean_text_for_tts(text)
        lines = result.split("\n")
        for line in lines:
            if line.strip():
                assert len(line.strip()) > 3, f"Line too short: '{line}'"

    def test_clean_text_for_tts_converts_numbers_to_words(self):
        """Test number-to-words conversion integration."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "In 2013, 1,500 people attended at 3.14pm"
        result = clean_text_for_tts(text)

        assert "2013" not in result
        assert "1,500" not in result
        assert "3.14" not in result
        # Spanish words should appear
        assert "dos mil trece" in result or "mil quinientas" in result

    def test_clean_text_for_tts_converts_numbers_disabled(self):
        """Test with convert_numbers=False."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "In 2013, there were 1,500 items"
        result = clean_text_for_tts(text, convert_numbers=False)

        # Numbers should remain as digits
        assert "2013" in result
        assert "1,500" in result

    def test_clean_text_for_tts_html_entity_decoding(self):
        """Test HTML entity decoding."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "Space&nbsp;here&nbsp;&nbsp;and &amp; or &lt; &gt;"
        result = clean_text_for_tts(text)
        assert "&nbsp;" not in result
        assert "&amp;" not in result
        assert "&lt;" not in result
        assert "&gt;" not in result
        assert " and " in result or "y " in result  # &amp; -> y

    def test_clean_text_for_tts_special_pronunciation_corrections(self):
        """Test pronunciation corrections for problematic words."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "Washington and Silicon Valley"
        result = clean_text_for_tts(text)
        assert "Washington" not in result
        assert "Silicon Valley" not in result
        assert "Wáshington" in result
        assert "Sílicon Valey" in result

    def test_clean_text_for_tts_removes_h_tags(self):
        """Test removal of h1 and h2 tags."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "<h1>Title</h1><h2>Subtitle</h2>"
        result = clean_text_for_tts(text)
        assert "<h1>" not in result
        assert "<h2>" not in result
        assert "Title" in result
        assert "Subtitle" in result

    def test_clean_text_for_tts_removes_strong_tags(self):
        """Test removal of strong tags."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "<strong>Bold</strong> text"
        result = clean_text_for_tts(text)
        assert "<strong>" not in result
        assert "</strong>" not in result
        assert "Bold" in result
        assert "text" in result

    def test_clean_text_for_tts_preserves_accents(self):
        """Test that accents are preserved."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "Año 2024 con acentos: á é í ó ú"
        result = clean_text_for_tts(text)
        assert "á" in result or "Año" in result

    def test_clean_text_for_tts_language_parameter(self):
        """Test different language parameter (non-Spanish)."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        # English conversion
        text = "42"
        result_es = clean_text_for_tts("42", language="es")
        result_en = clean_text_for_tts("42", language="en")

        assert "cuarenta" in result_es or "cuarenta y dos" in result_es
        assert "forty" in result_en or "forty-two" in result_en

    def test_clean_text_for_tts_complex_realistic_text(self):
        """Test realistic article snippet."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        html_article = """
        <h1>Breaking News</h1>
        <p>In 2024, inflation reached 3.5% in Argentina. 
        The stock market gained 1,200 points. 
        Visit https://news.example.com for more.</p>
        <script>track();</script>
        <p>#economy #finance</p>
        """
        result = clean_text_for_tts(html_article)

        # Assertions
        assert "2024" not in result
        assert "3.5" not in result or "tres punto cinco" in result
        assert "1,200" not in result
        assert "https://" not in result
        assert "#economy" not in result
        assert "#finance" not in result
        assert "Breaking News" in result or "Breaking" in result
        assert "track()" not in result

    def test_clean_text_for_tts_whitespace_normalization(self):
        """Test whitespace normalization in various scenarios."""
        from src.shared.utils.text_cleaner import clean_text_for_tts

        text = "   Multiple    spaces   and\ttabs\n\nnewlines   "
        result = clean_text_for_tts(text)
        # No double spaces
        assert "  " not in result
        # Trimmed
        assert not result.startswith(" ")
        assert not result.endswith(" ")
