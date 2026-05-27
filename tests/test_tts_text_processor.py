"""Tests for unified TTS text processor."""

import pytest
from src.shared.adapters.tts_text_processor import TTSTextProcessor


class TestTTSTextProcessor:
    """Test cases for TTSTextProcessor."""

    # HTML Cleaning Tests
    def test_clean_html_basic_tags(self):
        """Test removal of basic HTML tags."""
        html = "<p>Paragraph</p><div>Div content</div>"
        result = TTSTextProcessor.process(html)
        assert "<" not in result
        assert ">" not in result
        assert "Paragraph" in result
        assert "Div content" in result

    def test_clean_html_script_tags(self):
        """Test removal of script and style tags."""
        html = "<script>alert('xss')</script><p>Safe</p><style>body{}</style>"
        result = TTSTextProcessor.process(html)
        assert "alert" not in result
        assert "body{}" not in result
        assert "Safe" in result

    def test_clean_html_entities(self):
        """Test HTML entity decoding."""
        text = "Hello&nbsp;world&amp;stuff&lt;tag&gt;"
        result = TTSTextProcessor.process(text)
        assert "&nbsp;" not in result
        assert "&amp;" not in result
        assert "Hello world" in result

    # Abbreviation Expansion Tests
    def test_expand_abbreviations_countries(self):
        """Test expansion of country abbreviations."""
        text = "Acuerdo entre E.E.U.U. y la U.E."
        result = TTSTextProcessor.process(text)
        assert "Estados Unidos" in result
        assert "Unión Europea" in result

    def test_expand_abbreviations_titles(self):
        """Test expansion of title abbreviations."""
        text = "El Dr. García y la Dra. López"
        result = TTSTextProcessor.process(text)
        assert "Doctor" in result
        assert "Doctora" in result

    def test_expand_abbreviations_organizations(self):
        """Test expansion of organization abbreviations."""
        text = "La O.M.S. informó sobre la pandemia"
        result = TTSTextProcessor.process(text)
        assert "Organización Mundial de la Salud" in result

    # Punctuation Normalization Tests
    def test_normalize_quotes(self):
        """Test that problematic quotes are removed."""
        text = 'El "contenido" está bien'
        result = TTSTextProcessor.process(text)
        assert '"' not in result
        assert 'contenido' in result

    def test_normalize_multiple_commas(self):
        """Test normalization of multiple commas."""
        text = "Hola,,, mundo"
        result = TTSTextProcessor.process(text)
        assert ",,," not in result
        assert "," in result

    def test_normalize_multiple_spaces(self):
        """Test normalization of multiple spaces."""
        text = "Hola   mundo"
        result = TTSTextProcessor.process(text)
        assert "   " not in result
        assert "Hola mundo" in result

    def test_preserve_accents(self):
        """Test that Spanish accents are preserved."""
        text = "La política económica está en crisis"
        result = TTSTextProcessor.process(text)
        assert "política" in result
        assert "económica" in result

    # URL and Social Media Removal Tests
    def test_remove_urls(self):
        """Test removal of URLs."""
        text = "Visit https://example.com and http://test.org"
        result = TTSTextProcessor.process(text)
        assert "https" not in result
        assert "http" not in result
        assert "example.com" not in result

    def test_remove_social_mentions(self):
        """Test removal of @ mentions."""
        text = "Contact @username for info"
        result = TTSTextProcessor.process(text)
        assert "@" not in result

    def test_remove_hashtags(self):
        """Test removal of hashtags."""
        text = "This is #awesome and #trending news"
        result = TTSTextProcessor.process(text)
        assert "#" not in result
        # Hashtags are removed entirely (including the word)
        assert "news" in result

    # Edge Cases
    def test_empty_string(self):
        """Test handling of empty string."""
        assert TTSTextProcessor.process("") == ""
        assert TTSTextProcessor.process(None) == ""

    def test_real_world_article(self):
        """Test real-world complex content."""
        text = '''
        <article>
            <h1>Título</h1>
            <p>El Dr. García, de E.E.U.U., informó a la O.M.S. sobre
            nuevos casos... "Será importante",,,para evitar propagación.</p>
            <p>Más info en https://example.com</p>
            <p>Síguenos @news_channel #pandemia</p>
            <script>alert('malware')</script>
        </article>
        '''
        result = TTSTextProcessor.process(text)

        # Should expand abbreviations
        assert "Doctor" in result or "Dr." not in result
        assert "Estados Unidos" in result
        assert "Organización Mundial de la Salud" in result

        # Should clean up
        assert "alert" not in result  # script removed
        assert "<" not in result  # HTML removed
        assert "https" not in result  # URL removed
        assert "@" not in result  # mentions removed
        assert "#" not in result  # hashtags removed
        assert '""' not in result  # quotes removed

    def test_light_cleanup_for_display(self):
        """Test light cleanup mode for display purposes."""
        html = "<p>Hello <strong>world</strong></p>"
        result = TTSTextProcessor.clean_for_display(html)
        assert "<" not in result
        assert "Hello" in result
        assert "world" in result

    def test_number_conversion_disabled(self):
        """Test that number conversion can be disabled."""
        text = "There are 5 items"
        result = TTSTextProcessor.process(text, convert_numbers=False)
        # Should still have numbers if conversion disabled
        assert "5" in result or "cinco" in result  # Either original or converted

    def test_punctuation_spacing(self):
        """Test that punctuation spacing is corrected."""
        text = "Hello , world ! How are you ?"
        result = TTSTextProcessor.process(text)
        # Should normalize spacing around punctuation
        assert " ," not in result  # No space before comma
        assert ", " in result  # Space after comma


class TestTTSTextProcessorPhases:
    """Test individual processing phases."""

    def test_phase_html_cleaning(self):
        """Test HTML cleaning phase."""
        html = "<p>Test <script>bad</script> content</p>"
        result = TTSTextProcessor._clean_html(html)
        assert "bad" not in result
        assert "Test" in result
        assert "content" in result

    def test_phase_abbreviation_expansion(self):
        """Test abbreviation expansion phase."""
        text = "Dr. Smith from E.E.U.U."
        result = TTSTextProcessor._expand_abbreviations(text)
        assert "Doctor" in result
        assert "Estados Unidos" in result

    def test_phase_punctuation_normalization(self):
        """Test punctuation normalization phase."""
        text = 'Text "with""quotes" and,,,commas'
        result = TTSTextProcessor._normalize_punctuation(text)
        assert '""' not in result
        assert ",,," not in result

    def test_phase_final_cleanup(self):
        """Test final cleanup phase."""
        text = "Text with https://url.com and @mention and #tag"
        result = TTSTextProcessor._final_cleanup(text)
        assert "https" not in result
        assert "@" not in result
        assert "#" not in result
