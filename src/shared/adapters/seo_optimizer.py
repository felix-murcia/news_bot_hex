"""SEO utilities for WordPress publishing pipeline."""

import re
import json
import unicodedata
from typing import Optional


_STOP_WORDS_ES = {
    "a", "al", "ante", "bajo", "con", "contra", "de", "del", "desde", "durante",
    "el", "en", "entre", "hacia", "hasta", "la", "las", "lo", "los", "mediante",
    "para", "por", "que", "se", "sin", "sobre", "tras", "un", "una", "uno", "unos",
    "unas", "y", "e", "o", "u", "ni", "pero", "sino", "como", "mas", "ya", "muy",
    "su", "sus", "es", "son", "fue", "han", "ha", "hay", "no", "si", "me", "te",
    "le", "nos", "les", "este", "esta", "estos", "estas", "ese", "esa", "esos",
    "esas", "aquel", "aquella", "aquellos", "aquellas", "tras", "dice", "dicen",
    "segun", "afirma", "afirman", "indica", "indican",
}


def slugify(text: str, max_words: int = 6) -> str:
    """Build an SEO slug using the first max_words significant words.

    Avoids truncating words mid-character. Strips accents and special chars.
    """
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    words = text.split()
    significant = [w for w in words if w not in _STOP_WORDS_ES and len(w) >= 3]
    chosen = significant[:max_words] if significant else words[:max_words]
    return "-".join(chosen)


def extract_focus_keyphrase(title: str, max_words: int = 5) -> str:
    """Extract a natural focus keyphrase from the title (4-5 significant words)."""
    words = re.findall(r"\b[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{3,}\b", title)
    significant = [w.lower() for w in words if w.lower() not in _STOP_WORDS_ES]
    return " ".join(significant[:max_words]) if significant else title.lower()[:60]


def generate_meta_description(title: str, first_paragraph: str, max_chars: int = 155) -> str:
    """Generate a CTR-optimised meta description.

    Strategy:
    - Lead with a concise restatement of the title hook (who/what/where).
    - Append a fragment of the opening paragraph for context.
    - Stay within max_chars.
    """
    clean_title = re.sub(r"[.!?]+$", "", title.strip())
    clean_para = re.sub(r"<[^>]+>", " ", first_paragraph)
    clean_para = re.sub(r"\s+", " ", clean_para).strip()

    # Remove the title text from the paragraph to avoid duplication
    title_words = set(clean_title.lower().split())
    para_sentences = re.split(r"(?<=[.!?])\s+", clean_para)
    context = ""
    for sent in para_sentences:
        sent_words = set(sent.lower().split())
        overlap = len(title_words & sent_words) / max(len(title_words), 1)
        if overlap < 0.5 and len(sent) > 20:
            context = sent
            break

    if context:
        candidate = f"{clean_title}. {context}"
    else:
        candidate = clean_para

    if len(candidate) <= max_chars:
        return candidate

    # Truncate at last complete word within limit
    truncated = candidate[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > 80:
        truncated = truncated[:last_space]
    return truncated.rstrip(".,;:") + "…"


def truncate_seo_title(title: str, max_chars: int = 60) -> str:
    """Return a SERP-safe SEO title (max_chars, no trailing punctuation)."""
    title = re.sub(r"[.]+$", "", title.strip())
    if len(title) <= max_chars:
        return title
    truncated = title[:max_chars]
    last_sep = max(truncated.rfind(" "), truncated.rfind(":"), truncated.rfind("—"))
    if last_sep > 30:
        truncated = truncated[:last_sep]
    return truncated.rstrip(".,;:- ")


def clean_title(title: str) -> str:
    """Remove trailing punctuation added automatically by the pipeline."""
    return re.sub(r"[.]+$", "", title.strip())


def generate_excerpt(first_paragraph: str, max_chars: int = 380) -> str:
    """Build an excerpt from the first paragraph ending at a sentence boundary.

    Takes up to max_chars characters, always ending at the last complete sentence
    within that limit. Falls back to word boundary if no sentence found.
    """
    text = re.sub(r"<[^>]+>", " ", first_paragraph)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) <= max_chars:
        return text

    window = text[:max_chars]
    # Find last sentence-ending punctuation within the window
    last_sentence = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    if last_sentence > 80:
        return window[: last_sentence + 1].strip()

    # No sentence boundary — truncate at last word
    last_space = window.rfind(" ")
    return (window[:last_space] if last_space > 80 else window).rstrip(".,;:") + "…"


def build_news_article_schema(
    title: str,
    description: str,
    url: str,
    image_url: str,
    date_published: str,
    author_name: str = "NBES Redacción",
    publisher_name: str = "NBES",
    publisher_logo: str = "https://nbes.blog/wp-content/uploads/logo.png",
) -> str:
    """Return a NewsArticle JSON-LD script block ready to inject into post content."""
    schema = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": title[:110],
        "description": description[:200],
        "url": url,
        "datePublished": date_published,
        "dateModified": date_published,
        "author": {
            "@type": "Organization",
            "name": author_name,
        },
        "publisher": {
            "@type": "Organization",
            "name": publisher_name,
            "logo": {
                "@type": "ImageObject",
                "url": publisher_logo,
            },
        },
        "image": {
            "@type": "ImageObject",
            "url": image_url,
        },
        "inLanguage": "es",
    }
    encoded = json.dumps(schema, ensure_ascii=False)
    return f'\n<!-- wp:html -->\n<script type="application/ld+json">{encoded}</script>\n<!-- /wp:html -->\n'
