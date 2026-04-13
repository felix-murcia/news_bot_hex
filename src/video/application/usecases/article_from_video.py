import os
import logging
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Any

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("video_bot.usecase.article_from_video")

DATA_DIR = Settings.DATA_DIR
VIDEO_ARTICLES_PATH = DATA_DIR / "generated_video_articles.json"
VIDEO_POSTS_PATH = DATA_DIR / "generated_video_posts.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def slugify(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def limpiar(texto: str) -> str:
    if not texto:
        return ""
    return str(texto).strip().strip("*").strip('"').strip()


class ArticleFromVideoUseCase:
    """Caso de uso para generar artículo desde transcripción de video."""

    def __init__(
        self,
        llm_provider: str = Settings.AI_PROVIDER,
        llm_config: dict = None,
    ):
        self.llm_provider = llm_provider
        self.llm_config = llm_config or {}
        self._ai_model = None

    def _get_ai_model(self):
        """Lazy load AI model."""
        if self._ai_model is None:
            from src.shared.adapters.ai.ai_factory import get_ai_adapter

            self._ai_model = get_ai_adapter(self.llm_provider, self.llm_config)
        return self._ai_model

    def execute(self, transcript: str, url: str, tema: str) -> Dict[str, Any]:
        """Ejecuta el caso de uso."""
        return self._generate_article(transcript, url, tema)

    def _generate_article(self, transcript: str, url: str, tema: str) -> Dict[str, Any]:
        """Genera artículo desde transcripción de video usando agentes centralizados."""
        from src.shared.adapters.ai.agents import ArticleFromContentAgent
        from src.shared.adapters.translator import translate_text
        from src.shared.adapters.web_search import enriquecer_con_contexto

        transcerpt_es = translate_text(transcript[:10000], target_lang="es")

        # Enriquecer con búsqueda web si está disponible
        web_context = enriquecer_con_contexto(transcript, tema)
        if web_context:
            logger.info(f"[ARTICLE_VIDEO] Contexto web añadido: {len(web_context)} chars")

        model = self._get_ai_model()
        agent = ArticleFromContentAgent(model, source_type="video")

        content = agent.generate(transcript[:10000], tema=tema, web_context=web_context)

        # Aplicar post-edición automática al artículo
        from src.shared.utils.content_post_editor import post_edit_content
        content = post_edit_content(content)

        # El prompt prohibe <h1>, así que extraemos del primer <h2>
        title_match = re.search(r"<h2>(.*?)</h2>", content, re.DOTALL)
        title = title_match.group(1).strip() if title_match else f"Video: {tema}"

        return self._build_article_response(content, title, url, tema)

    def _generate_unique_slug(self, title: str, content: str, tema: str) -> str:
        """Generate a unique, SEO-friendly slug from title and content."""
        # Extract first 150 chars of content for additional keywords
        text_only = re.sub(r"<[^>]+>", " ", content)[:150]
        
        # Combine title and content snippet
        combined = f"{title} {text_only}".lower()
        
        # Remove common generic prefixes like "video:", "audio:", etc.
        combined = re.sub(r"^(video|audio|podcast|noticia)[:\s]+", "", combined)
        
        # Extract meaningful words (3+ chars, no stopwords)
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
        
        # Take first 5-6 meaningful words for slug
        slug_words = meaningful[:6] if len(meaningful) >= 5 else meaningful[:4]
        
        # Fallback: use tema + first few words
        if len(slug_words) < 3:
            slug_words = [slugify(tema)] + words[:4]
        
        slug = "-".join(slug_words)[:80]  # Max 80 chars for SEO
        
        # Ensure slug is clean
        slug = re.sub(r'-+', '-', slug).strip('-')
        
        return slug or slugify(f"{tema}-{title[:30]}")

    def _build_article_response(
        self, content: str, title: str, url: str, tema: str
    ) -> Dict[str, Any]:
        """Construye la respuesta del artículo."""
        # Generate a more descriptive and unique slug
        slug = self._generate_unique_slug(title, content, tema)

        content_clean = content
        content_clean = re.sub(r"^```html\s*", "", content_clean, flags=re.MULTILINE)
        content_clean = re.sub(r"^```\s*$", "", content_clean, flags=re.MULTILINE)
        content_clean = content_clean.strip()

        # Remover el primer <h2> si coincide con el título extraído
        # (porque será usado como <h1> por WordPress)
        first_h2_match = re.search(r"^<h2[^>]*>(.*?)</h2>", content_clean, re.DOTALL | re.IGNORECASE)
        if first_h2_match:
            first_h2_content = first_h2_match.group(1).strip()
            # Comparar los primeros 80 caracteres para tolerancia
            if first_h2_content[:80].lower() == title[:80].lower():
                content_clean = re.sub(r"^<h2[^>]*>.*?</h2>\s*", "", content_clean, flags=re.DOTALL | re.IGNORECASE)
                logger.info(f"[ARTICLE_VIDEO] Primer <h2> removido (será usado como <h1>): {title[:50]}...")

        text_only = re.sub(r"<[^>]+>", " ", content_clean)
        first_p = text_only.split("\n")[0][:160] if text_only else ""

        tweet = self._generate_tweet(content_clean, title, tema, url)

        article = {
            "title": title,
            "title_es": title,
            "slug": slug,
            "content": content_clean,
            "desc": first_p,
            "excerpt": first_p,
            "labels": [tema],
            "source_type": "video_man",
            "image_url": "https://api.nbes.blog/image-310/",
            "image_credit": "NBES",
            "alt_text": title,
            "url": f"https://nbes.blog/{slug}",
            "original_url": url,
        }

        parrafos = len(re.findall(r"<p>", content_clean))
        subtitulos = len(re.findall(r"<h2>", content_clean))

        return {
            "article": article,
            "tweet": tweet,
            "mode": self.llm_provider,
            "stats": {"parrafos": parrafos, "subtitulos": subtitulos},
        }

    def _generate_tweet(self, content: str, title: str, tema: str, url: str) -> str:
        """Genera tweet profesional usando agente centralizado."""
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
        
        # Limpieza de patrones no deseados
        tweet = re.sub(r"\[HASHTAGS\]", "", tweet, flags=re.IGNORECASE)
        tweet = re.sub(r"^\s*#\w+\s*$", "", tweet, flags=re.MULTILINE)
        tweet = tweet.strip()

        from src.shared.utils.tweet_truncation import truncate_social_post

        tweet = truncate_social_post(tweet)

        # Aplicar post-edición automática
        from src.shared.utils.content_post_editor import post_edit_content
        tweet = post_edit_content(tweet)

        if not tweet:
            logger.error(
                f"[VIDEO] Tweet generado vacío para: {title[:80]}... "
                f"(tema: {tema}). Se aborta la publicación."
            )
            raise RuntimeError(
                f"Tweet vacío para '{title[:80]}...'. No se publica contenido de baja calidad."
            )

        return tweet


def run_from_video(
    transcript: str,
    url: str = "",
    tema: str = "Videos",
    llm_provider: str = Settings.AI_PROVIDER,
    llm_config: Dict = None,
) -> Dict[str, Any]:
    """Función principal."""
    logger.info(f"[ARTICLE_VIDEO] Ejecutando con {llm_provider}")
    use_case = ArticleFromVideoUseCase(
        llm_provider=llm_provider,
        llm_config=llm_config,
    )
    return use_case.execute(transcript, url, tema)


def main():
    import argparse
    import time

    parser = argparse.ArgumentParser(
        description="Generar artículo desde transcripción de video"
    )
    parser.add_argument(
        "--transcript", type=str, required=True, help="Archivo con transcripción"
    )
    parser.add_argument("--url", type=str, default="", help="URL del video")
    parser.add_argument("--tema", type=str, default="Videos", help="Tema del artículo")
    parser.add_argument(
        "--model",
        type=str,
        default=Settings.AI_PROVIDER,
        choices=Settings.SUPPORTED_AI_PROVIDERS,
        help="Modelo de IA a usar",
    )

    args = parser.parse_args()

    if os.path.exists(args.transcript):
        with open(args.transcript, "r", encoding="utf-8") as f:
            transcript = f.read()
    else:
        transcript = args.transcript

    start_time = time.time()

    try:
        results = run_from_video(
            transcript=transcript,
            url=args.url,
            tema=args.tema,
            llm_provider=args.model,
        )

        elapsed = time.time() - start_time

        print(f"\n✅ Artículo desde video generado en {elapsed:.1f}s")
        print(f"📰 Título: {results['article']['title']}")
        print(f"📊 Proveedor: {results.get('mode', 'desconocido')}")
        print(
            f"📈 Estructura: {results['stats']['parrafos']}p/{results['stats']['subtitulos']}h2"
        )
        print(f"🔗 Guardado en: {VIDEO_ARTICLES_PATH}")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
