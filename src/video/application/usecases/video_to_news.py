import os
import uuid
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

from src.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger("video_bot")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def check_copyright(url: str) -> bool:
    """Verifica riesgo de copyright."""
    copyright_domains = ["youtube.com", "youtu.be", "tiktok.com", "instagram.com"]
    return any(domain in url.lower() for domain in copyright_domains)


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
        use_ai: bool = True,
        model_provider: str = "openrouter",
        ai_config: dict = None,
        ai_model=None,
    ):
        self.use_ai = use_ai
        self.model_provider = model_provider
        self.ai_config = ai_config or {}
        self.ai_model = ai_model

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

        from src.video.infrastructure.adapters.video_fetcher import download_video

        if not video_path.exists():
            logger.info(f"[VIDEO] Descargando video: {url}")
            video_path = download_video(url)
            if not video_path:
                raise ValueError(f"No se pudo descargar el video: {url}")

        if not validate_video(video_path):
            raise ValueError(
                f"El video no tiene audio. No se puede transcribir: {video_path}"
            )

        logger.info(f"[VIDEO] Transcribiendo video")
        from src.video.infrastructure.adapters.video_transcriber import transcribe_video

        transcript = transcribe_video(str(video_path))

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

            slug = slugify(title[:50])

            article = {
                "title": title,
                "title_es": title,
                "content": content,
                "desc": transcript[:500],
                "slug": slug,
                "labels": [tema],
                "source_type": "video_man",
                "url": f"https://nbes.blog/{slug}",
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

        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        tweet = tweet.strip()

        if not tweet:
            logger.error(
                f"[VIDEO] Tweet generado vacío para: {title[:80]}... "
                f"Se aborta la publicación."
            )
            raise RuntimeError(
                f"Tweet vacío para '{title[:80]}...'. No se publica contenido de baja calidad."
            )

        return tweet

    def _save_outputs(
        self,
        article_data: Dict,
        transcript: str,
        video_path: Path,
        transcript_path: Path,
    ):
        """Guarda los outputs."""
        article = article_data.get("article", {})

        articles_path = DATA_DIR / "generated_video_articles.json"
        posts_path = DATA_DIR / "generated_video_posts.json"

        with open(articles_path, "w", encoding="utf-8") as f:
            json.dump([article], f, indent=2, ensure_ascii=False)

        with open(posts_path, "w", encoding="utf-8") as f:
            json.dump(
                [{"tweet": "", "article": article}], f, indent=2, ensure_ascii=False
            )

        logger.info(f"[VIDEO] Archivos guardados en {DATA_DIR}")

    def process_video_url(self, url: str) -> Dict[str, Any]:
        """Procesa un video y genera artículo."""
        logger.info(f"[VIDEO] Procesando video: {url}")

        if check_copyright(url):
            logger.warning(f"[VIDEO] Posible riesgo de copyright: {url}")

        file_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
        video_path = CACHE_DIR / f"{file_id}.mp4"
        transcript_path = CACHE_DIR / f"{file_id}.txt"

        transcript = self._get_or_create_transcript(url, video_path, transcript_path)

        article_data = self._generate_article(transcript, url)

        tweet_text = self._generate_tweet(article_data)

        self._save_outputs(article_data, transcript, video_path, transcript_path)

        result = {
            "transcript": transcript,
            "transcript_file": str(transcript_path),
            "article": article_data["article"].get("content", ""),
            "article_file": str(DATA_DIR / "generated_video_articles.json"),
            "post": tweet_text,
            "mode": self.model_provider,
        }

        logger.info("[VIDEO] Procesamiento completado")
        return result


def process_video_url(
    url: str,
    model_provider: str = "openrouter",
    use_ai: bool = True,
    ai_config: dict = None,
) -> Dict[str, Any]:
    """Función principal."""
    processor = VideoToNewsUseCase(
        model_provider=model_provider,
        use_ai=use_ai,
        ai_config=ai_config,
    )
    return processor.process_video_url(url)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Procesar video y generar artículo")
    parser.add_argument("url", help="URL del video")
    parser.add_argument(
        "--model",
        type=str,
        default="openrouter",
        choices=["gemini", "openrouter", "local", "mock"],
        help="Modelo de IA a usar",
    )
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")

    args = parser.parse_args()

    result = process_video_url(
        url=args.url,
        model_provider=args.model,
        use_ai=not args.local,
    )
    print(f"✅ Procesado: {args.url}")
    print(f"📄 Artículo: {len(result['article'])} caracteres")


if __name__ == "__main__":
    main()
