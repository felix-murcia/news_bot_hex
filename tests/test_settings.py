"""Tests for settings configuration (B5: groq in SUPPORTED_AI_PROVIDERS)."""

def test_groq_in_supported_providers():
    """GROQ must be in SUPPORTED_AI_PROVIDERS (B5 fix)."""
    # Read the source file directly to avoid import-time side effects
    with open("config/settings.py") as f:
        content = f.read()

    # Verify groq is in the list
    assert '"groq"' in content, "groq not found in settings.py"
    assert "SUPPORTED_AI_PROVIDERS" in content, "SUPPORTED_AI_PROVIDERS not found"
    
    # Check the specific line
    import re
    match = re.search(r'SUPPORTED_AI_PROVIDERS\s*=\s*\[([^\]]+)\]', content)
    assert match, "SUPPORTED_AI_PROVIDERS pattern not found"
    providers = match.group(1)
    assert '"groq"' in providers, f"groq not in SUPPORTED_AI_PROVIDERS: {providers}"
    
    # Also verify AI_ADAPTER_MAP has groq
    assert '"groq":' in content, "groq not in AI_ADAPTER_MAP"
    assert "GroqAdapter" in content, "GroqAdapter not found"

    print("✓ groq in SUPPORTED_AI_PROVIDERS")
    print("✓ groq in AI_ADAPTER_MAP")
    print("✓ GroqAdapter mapped")

if __name__ == "__main__":
    test_groq_in_supported_providers()
    print("\nAll B5 tests passed!")