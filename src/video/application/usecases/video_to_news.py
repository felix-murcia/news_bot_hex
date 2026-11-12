import uuid
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging
from src.shared.domain.ports.debug_output_repository import DebugOutputRepository

logger = logging.getLogger(__name__)
def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def check_copyright(url: str, domains: List[str]) -> bool:
    """Verifica riesgo de copyright."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in domains)


def validate_video(video_path: Path) -> bool:
    """Valida que el video tiene audio."""
    try:
        if not video_path.exists():
            logger.warning(f"[VIDEO] Video no encontrado: {video_path}")
            return False
        from src.video.infrastructure.adapters.video_transcriber import has_audio_stream

        if not has_audio_stream(str(video_path)):
            logger.warning(f"[VIDEO] El video no tiene pista de audio: {video_path}")
            return False
        return True
    except Exception as e:
        logger.error(f"[VIDEO] Error validando video {video_path}: {e}")
        return False


class VideoToNewsUseCase:
    """Caso de uso para procesar videos y generar artículos."""

    def __init__(
        self,
        debug_output_repo: DebugOutputRepository,
        cache_dir: Path,
        wp_site_url: str,
        copyright_domains: List[str],
        use_ai: bool = True,
        model_provider: str = "gemini",
        ai_config: Optional[dict] = None,
        ai_model=None,
    ):
        self.use_ai = use_ai
        self.model_provider = model_provider
        self.ai_config = ai_config or {}
        self.ai_model = ai_model
        self._debug_output_repo = debug_output_repo
        self._cache_dir = Path(cache_dir)
        self._wp_site_url = wp_site_url.rstrip("/")
        self._copyright_domains = list(copyright_domains)

    def _generate_unique_slug(self, title: str, content: str, tema: str) -> str:
        """Generate a unique, SEO-friendly slug from title and content."""
        text_only = re.sub(r"<[^>]+>", " ", content)[:150]
        combined = f"{title} {text_only}".lower()
        combined = re.sub(r"^(video|audio|podcast|noticia)[:\s]+", "", combined)

        stopwords_es = {
            "el",
            "la",
            "los",
            "las",
            "un",
            "una",
            "de",
            "del",
            "en",
            "y",
            "o",
            "que",
            "es",
            "son",
            "ser",
            "por",
            "para",
            "con",
            "sin",
            "se",
            "su",
            "sus",
            "al",
            "lo",
            "le",
            "les",
            "como",
            "más",
            "pero",
            "este",
            "esta",
            "todo",
            "todos",
            "ya",
            "muy",
            "también",
            "no",
            "si",
            "cuando",
            "donde",
            "the",
            "and",
            "for",
            "are",
            "but",
            "not",
            "you",
            "all",
            "can",
            "had",
            "her",
            "was",
            "one",
            "our",
            "out",
            "has",
            "have",
            "been",
            "from",
        }

        words = re.findall(r"[a-záéíóúñü]{4,}", combined)
        meaningful = [w for w in words if w not in stopwords_es]
        slug_words = meaningful[:6] if len(meaningful) >= 5 else meaningful[:4]

        if len(slug_words) < 3:
            slug_words = [slugify(tema)] + words[:4]

        slug = "-".join(slug_words)[:80]
        slug = re.sub(r"-+", "-", slug).strip("-")

        return slug or slugify(f"{tema}-{title[:30]}")

    def _get_ai_model(self):
        """Obtiene el modelo de IA (lazy loading)."""
        if self.ai_model is None:
            from src.shared.adapters.ai.ai_factory import get_ai_adapter

            provider = self.model_provider if self.use_ai else "mock"
            self.ai_model = get_ai_adapter(provider, self.ai_config)
            logger.info(f"[VIDEO] Adapter '{provider}' instanciado")
        return self.ai_model

    def _get_or_create_transcript(
        self, url: str, video_path: Path, transcript_path: Path
    ) -> str:
        """Obtiene transcripción desde caché o la genera."""
        if transcript_path.exists():
            logger.info(f"[VIDEO] Reutilizando transcripción cacheada")
            return transcript_path.read_text(encoding="utf-8")

        from src.video.infrastructure.adapters.video_fetcher import download_mp3

        logger.info(f"[VIDEO] Descargando audio MP3 del video: {url}")
        audio_path = download_mp3(url)
        if not audio_path:
            raise ValueError(f"No se pudo descargar el audio del video: {url}")

        logger.info(f"[VIDEO] Transcribiendo audio MP3")
        from src.video.infrastructure.adapters.video_transcriber import transcribe_audio

        transcript = transcribe_audio(audio_path)

        transcript_path.write_text(transcript, encoding="utf-8")
        logger.info(f"[VIDEO] Transcripción guardada")
        return transcript

    def _generate_article(
        self, transcript: str, url: str, tema: str = "Videos"
    ) -> Dict[str, Any]:
        """Genera artículo desde transcripción."""
        try:
            from src.shared.adapters.ai.agents import ArticleFromContentAgent

            model = self._get_ai_model()
            agent = ArticleFromContentAgent(model, source_type="transcript")

            content = agent.generate(transcript[:4000], tema=tema)

            title_match = re.search(r"<h1>(.*?)</h1>", content, re.DOTALL)
            title = title_match.group(1).strip() if title_match else "Video Noticia"

            slug = self._generate_unique_slug(title, content, tema)

            article = {
                "title": title,
                "title_es": title,
                "content": content,
                "desc": transcript[:500],
                "slug": slug,
                "labels": [tema],
                "source_type": "video_man",
                "url": f"{self._wp_site_url}/{slug}" if self._wp_site_url else slug,
                "original_url": url,
            }

            return {"article": article, "news_item": article}

        except Exception as e:
            logger.error(f"[VIDEO] Error generando artículo: {e}")
            lines = transcript.split("\n")[:20]
            body = "<h1>Video Noticia</h1>\n"
            for i, line in enumerate(lines):
                if i % 4 == 0 and i > 0:
                    body += "<h2>Punto clave</h2>\n"
                body += f"<p>{line.strip()}</p>\n"

            return {
                "article": {
                    "title": "Video Noticia",
                    "title_es": "Video Noticia",
                    "content": body,
                    "slug": slugify("video-noticia"),
                    "labels": [tema],
                    "source_type": "video_man",
                },
                "news_item": {},
            }

    def _generate_tweet(self, article_data: Dict) -> str:
        """Genera tweet desde artículo."""
        from src.shared.adapters.ai.agents import TweetAgent

        title = article_data.get("article", {}).get("title", "Video Noticia")

        model = self._get_ai_model()
        agent = TweetAgent(model)
        tweet = agent.generate(f"Video: {title[:100]}")

        from src.shared.adapters.social_post_adapter import truncate_social_post

        tweet = truncate_social_post(tweet)

        # Aplicar post-edición automática
        from src.shared.adapters.content_post_editor import post_edit_content

        tweet = post_edit_content(tweet)

        if not tweet:
            logger.error(
                f"[VIDEO] Tweet generado vacío para: {title[:80]}... "
                f"Se aborta la publicación."
            )
            raise RuntimeError(
                f"Tweet vacío para '{title[:80]}...'. No se publica contenido de baja calidad."
            )

        return tweet

    def _save_outputs(self, article_data: Dict) -> Path:
        """Guarda los outputs."""
        article_path = self._debug_output_repo.save_outputs(
            "video", article_data, {"tweet": ""}
        )
        logger.info(f"[VIDEO] Archivos guardados en {article_path.parent}")
        return article_path

    def process_video_url(self, url: str) -> Dict[str, Any]:
        """Procesa un video y genera artículo."""
        logger.info(f"[VIDEO] Procesando video: {url}")

        if check_copyright(url, self._copyright_domains):
            logger.warning(f"[VIDEO] Posible riesgo de copyright: {url}")

        file_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
        video_path = self._cache_dir / f"{file_id}.mp4"
        transcript_path = self._cache_dir / f"{file_id}.txt"

        transcript = self._get_or_create_transcript(url, video_path, transcript_path)

        article_data = self._generate_article(transcript, url)

        tweet_text = self._generate_tweet(article_data)

        article_path = self._save_outputs(article_data)

        result = {
            "transcript": transcript,
            "transcript_file": str(transcript_path),
            "article": article_data["article"].get("content", ""),
            "article_file": str(article_path),
            "post": tweet_text,
            "mode": self.model_provider,
        }

        logger.info("[VIDEO] Procesamiento completado")
        return result



