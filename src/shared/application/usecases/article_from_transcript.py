"""Article from Transcript Use Case.

Shared use case for generating articles and tweets from any transcript
(audio or video). Both pipelines delegate to this to ensure identical
quality and behavior.

Respects hexagonal architecture:
- Domain: article structure, slug generation
- Application: orchestration of adapters (AI, web search, translation)
- Infrastructure: AI adapters, web search, translator
"""

import re
from typing import Dict, Any, Optional

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("shared.usecase.article_from_transcript")

# Source type mapping for prompt selection
SOURCE_TYPE_MAP = {
    "audio": "transcript",
    "video": "video",
}

# Source type label for fallback titles
SOURCE_LABEL = {
    "audio": "Audio",
    "video": "Video",
}


def _slugify(text: str) -> str:
    """Generate a clean slug from text."""
    import unicodedata
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


class ArticleFromTranscriptUseCase:
    """Shared use case for generating articles from audio/video transcripts.

    Both audio and video pipelines use this to ensure identical quality.

    Usage:
        usecase = ArticleFromTranscriptUseCase(
            llm_provider=Settings.AI_PROVIDER,
            source_type="audio",  # or "video"
        )
        result = usecase.execute(transcript, url, tema)
    """

    def __init__(
        self,
        llm_provider: str = Settings.AI_PROVIDER,
        llm_config: Optional[dict] = None,
        source_type: str = "audio",
    ):
        self.llm_provider = llm_provider
        self.llm_config = llm_config or {}
        self.source_type = source_type  # "audio" or "video"
        self._ai_model = None

    def _get_ai_model(self):
        """Lazy load AI model."""
        if self._ai_model is None:
            from src.shared.adapters.ai.ai_factory import get_ai_adapter
            self._ai_model = get_ai_adapter(self.llm_provider, self.llm_config)
        return self._ai_model

    def execute(
        self, transcript: str, url: str, tema: str
    ) -> Dict[str, Any]:
        """Execute the transcript-to-article pipeline.

        Args:
            transcript: Transcribed text from audio or video.
            url: Original source URL.
            tema: Topic/category label.

        Returns:
            Dict with article, tweet, mode, and stats.
        """
        return self._generate_article(transcript, url, tema)

    def _generate_article(
        self, transcript: str, url: str, tema: str
    ) -> Dict[str, Any]:
        """Core article generation logic."""
        from src.shared.adapters.ai.agents import ArticleFromContentAgent
        from src.shared.adapters.translator import translate_text
        from src.shared.adapters.web_search import enriquecer_con_contexto

        # 1. Translate transcript to Spanish if needed
        transcerpt_es = translate_text(transcript[:10000], target_lang="es")

        # 2. Enrich with web context
        web_context = enriquecer_con_contexto(transcript, tema)
        if web_context:
            logger.info(
                f"[ARTICLE_TRANSCRIPT] Contexto web añadido: {len(web_context)} chars"
            )

        # 3. Generate article using shared agent
        model = self._get_ai_model()
        agent_type = SOURCE_TYPE_MAP.get(self.source_type, "transcript")
        agent = ArticleFromContentAgent(model, source_type=agent_type)

        content = agent.generate(
            transcript[:10000], tema=tema, web_context=web_context
        )

        # 4. Apply post-editing
        from src.shared.utils.content_post_editor import post_edit_content
        content = post_edit_content(content)

        # 5. Clean markdown fences if present
        content = re.sub(r"^```html\s*", "", content, flags=re.MULTILINE)
        content = re.sub(r"^```\s*$", "", content, flags=re.MULTILINE)
        content = content.strip()

        # 6. Extract title from first <h2> (prompt forbids <h1>)
        title_match = re.search(r"<h2>(.*?)</h2>", content, re.DOTALL)
        source_label = SOURCE_LABEL.get(self.source_type, "Noticia")
        title = title_match.group(1).strip() if title_match else f"{source_label}: {tema}"

        # 7. Remove first <h2> if it matches the extracted title
        # (WordPress will use it as <h1>, so we don't duplicate)
        first_h2_match = re.search(r"^<h2[^>]*>(.*?)</h2>", content, re.DOTALL | re.IGNORECASE)
        if first_h2_match:
            first_h2_content = first_h2_match.group(1).strip()
            if first_h2_content[:80].lower() == title[:80].lower():
                content = re.sub(
                    r"^<h2[^>]*>.*?</h2>\s*", "", content,
                    flags=re.DOTALL | re.IGNORECASE
                )
                logger.info(
                    f"[ARTICLE_TRANSCRIPT] Primer <h2> removido: {title[:50]}..."
                )

        # 8. Generate slug
        slug = self._generate_unique_slug(title, content, tema)

        # 9. Extract excerpt
        text_only = re.sub(r"<[^>]+>", " ", content)
        first_p = text_only.split("\n")[0][:160] if text_only else ""

        # 10. Generate tweet using AI agent
        tweet = self._generate_tweet(content, title, tema, url)

        # 11. Build article response
        article = {
            "title": title,
            "title_es": title,
            "slug": slug,
            "content": content,
            "desc": first_p,
            "excerpt": first_p,
            "labels": [tema],
            "source_type": f"{self.source_type}_man",
            "image_url": "https://api.nbes.blog/image-310/",
            "image_credit": "NBES",
            "alt_text": title,
            "url": f"https://nbes.blog/{slug}",
            "original_url": url,
        }

        # Count paragraphs: prefer <p> tags, fallback to text blocks
        parrafos = len(re.findall(r"<p>", content))
        if parrafos == 0:
            # LLM didn't use <p> tags — count text blocks instead
            text_blocks = [
                b.strip() for b in re.sub(r"<[^>]+>", "\n", content).split("\n")
                if b.strip()
            ]
            parrafos = len(text_blocks)

        subtitulos = len(re.findall(r"<h2>", content))
        word_count = len(re.sub(r"<[^>]+>", " ", content).split())

        logger.info(
            f"[ARTICLE_TRANSCRIPT] Artículo: {word_count} palabras, "
            f"{parrafos} párrafos, {subtitulos} subtítulos"
        )

        return {
            "article": article,
            "tweet": tweet,
            "mode": self.llm_provider,
            "stats": {"parrafos": parrafos, "subtitulos": subtitulos},
        }

    def _generate_unique_slug(
        self, title: str, content: str, tema: str
    ) -> str:
        """Generate a unique, SEO-friendly slug."""
        text_only = re.sub(r"<[^>]+>", " ", content)[:150]
        combined = f"{title} {text_only}".lower()
        combined = re.sub(
            r"^(video|audio|podcast|noticia)[:\s]+", "", combined
        )

        stopwords_es = {
            "el", "la", "los", "las", "un", "una", "de", "del", "en", "y", "o",
            "que", "es", "son", "ser", "por", "para", "con", "sin", "se", "su",
            "sus", "al", "lo", "le", "les", "como", "más", "pero", "este", "esta",
            "todo", "todos", "ya", "muy", "también", "no", "si", "cuando", "donde",
            "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
            "her", "was", "one", "our", "out", "has", "have", "been", "from",
        }

        words = re.findall(r'[a-záéíóúñü]{4,}', combined)
        meaningful = [w for w in words if w not in stopwords_es]
        slug_words = meaningful[:6] if len(meaningful) >= 5 else meaningful[:4]

        if len(slug_words) < 3:
            slug_words = [_slugify(tema)] + words[:4]

        slug = "-".join(slug_words)[:80]
        slug = re.sub(r'-+', '-', slug).strip('-')

        return slug or _slugify(f"{tema}-{title[:30]}")

    def _generate_tweet(
        self, content: str, title: str, tema: str, url: str
    ) -> str:
        """Generate professional tweet using TweetGeopoliticsAgent."""
        from src.shared.adapters.ai.agents import TweetGeopoliticsAgent

        clean = re.sub(r"<[^>]+>", " ", content)
        lines = [l.strip() for l in clean.split("\n") if l.strip()]
        context = lines[0][:300] if lines else title

        model = self._get_ai_model()
        agent = TweetGeopoliticsAgent(model)

        tweet = agent.generate(
            title=title,
            tema=tema,
            context=context[:200],
        )

        tweet = tweet.strip()

        # Clean unwanted patterns
        tweet = re.sub(r"\[HASHTAGS\]", "", tweet, flags=re.IGNORECASE)
        tweet = re.sub(r"^\s*#\w+\s*$", "", tweet, flags=re.MULTILINE)
        tweet = tweet.strip()

        from src.shared.utils.tweet_truncation import truncate_social_post
        tweet = truncate_social_post(tweet)

        # Apply post-editing
        from src.shared.utils.content_post_editor import post_edit_content
        tweet = post_edit_content(tweet)

        if not tweet:
            source_label = SOURCE_LABEL.get(self.source_type, "Contenido")
            logger.error(
                f"[ARTICLE_TRANSCRIPT] Tweet vacío para: {title[:80]}... "
                f"(tema: {tema}). Se aborta la publicación."
            )
            raise RuntimeError(
                f"Tweet vacío para '{title[:80]}...'. "
                f"No se publica contenido de baja calidad."
            )

        return tweet


def run_from_transcript(
    transcript: str,
    url: str = "",
    tema: str = "Noticias",
    llm_provider: str = Settings.AI_PROVIDER,
    llm_config: Optional[dict] = None,
    source_type: str = "audio",
) -> Dict[str, Any]:
    """Convenience function for generating article from transcript.

    Args:
        transcript: Transcribed text.
        url: Original source URL.
        tema: Topic/category.
        llm_provider: AI provider to use.
        llm_config: Provider-specific config.
        source_type: "audio" or "video".

    Returns:
        Dict with article, tweet, mode, and stats.
    """
    logger.info(
        f"[ARTICLE_TRANSCRIPT] Ejecutando ({source_type}, provider: {llm_provider})"
    )
    usecase = ArticleFromTranscriptUseCase(
        llm_provider=llm_provider,
        llm_config=llm_config,
        source_type=source_type,
    )
    return usecase.execute(transcript, url, tema)
