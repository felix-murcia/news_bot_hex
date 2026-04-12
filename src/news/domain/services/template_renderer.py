"""
Template Renderer for WordPress articles.

Domain service that renders articles using the newspaper template.
Template content is injected — no file system or HTTP dependencies.
"""

import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional


class TemplateRenderer:
    """
    Renders article HTML using the newspaper template.

    Template content is injected. No file system or HTTP dependencies.
    """

    def __init__(self, template_content: str):
        self._template = template_content

    @staticmethod
    def _get_domain(url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc or url
        except Exception:
            return url

    @staticmethod
    def _slugify(text: str) -> str:
        """Create URL-friendly slug."""
        text = text.lower()
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        return text.strip("-")

    def render(
        self,
        article_body_html: str,
        title: str,
        source_url: str = "",
        category: str = "Noticias",
        category_slug: str = "noticias",
        image_url: str = "",
        slug: str = "",
        excerpt: str = "",
    ) -> Dict[str, str]:
        """
        Render article with template.

        Args:
            article_body_html: Clean article HTML (without h1 title).
            title: Article title in Spanish.
            source_url: Original source URL.
            category: WordPress category name.
            category_slug: WordPress category slug.
            image_url: Image URL.
            slug: Article slug.
            excerpt: Short excerpt.

        Returns:
            Dict with rendered content and metadata.
        """
        if not slug:
            slug = self._slugify(title[:60])

        fecha_publicacion = datetime.now().strftime("%Y-%m-%d")
        try:
            fecha_path = datetime.strptime(fecha_publicacion, "%Y-%m-%d").strftime(
                "%Y/%m/%d"
            )
        except Exception:
            fecha_path = datetime.now().strftime("%Y/%m/%d")

        values = defaultdict(
            str,
            {
                "title": title,
                "article_body": article_body_html,
                "source_url": source_url,
                "source_domain": self._get_domain(source_url),
                "categoria_nombre": category,
                "categoria_slug": category_slug,
                "slug": slug,
                "fecha_path": fecha_path,
                "fecha_publicacion": fecha_publicacion,
            },
        )

        full_html = self._template.format_map(values)

        return {
            "content": full_html,
            "slug": slug,
            "image_url": image_url,
            "excerpt": excerpt,
            "category": category,
            "category_slug": category_slug,
        }
