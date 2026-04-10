import os
import uuid
import logging
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("audio_bot")

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
    copyright_domains = ["youtube.com", "youtu.be", "spotify.com", "apple.com"]
    return any(domain in url.lower() for domain in copyright_domains)


class AudioToNewsUseCase:
    """Caso de uso para procesar audio y generar artículos."""

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
            logger.info(f"[AUDIO] Adapter '{provider}' instanciado")
        return self.ai_model

    def _get_or_create_transcript(
        self, url: str, audio_path: Path, transcript_path: Path
    ) -> str:
        """Obtiene transcripción desde caché o la genera."""
        if transcript_path.exists():
            logger.info(f"[AUDIO] Reutilizando transcripción cacheada")
            return transcript_path.read_text(encoding="utf-8")

        from src.audio.infrastructure.adapters.audio_fetcher import (
            download_audio,
            has_audio_stream,
        )

        if not audio_path.exists():
            logger.info(f"[AUDIO] Descargando audio: {url}")
            audio_path = download_audio(url)
            if not audio_path:
                raise ValueError(f"No se pudo descargar el audio: {url}")
            audio_path = Path(audio_path)

        if not has_audio_stream(str(audio_path)):
            raise ValueError("El audio no tiene pista válida. No se puede transcribir.")

        logger.info(f"[AUDIO] Transcribiendo audio")
        from src.audio.infrastructure.adapters.audio_fetcher import transcribe_audio

        transcript = transcribe_audio(str(audio_path))

        transcript_path.write_text(transcript, encoding="utf-8")
        logger.info(f"[AUDIO] Transcripción guardada")
        return transcript

    def _generate_article(
        self, transcript: str, url: str, tema: str = "Audios"
    ) -> Dict[str, Any]:
        """Genera artículo desde transcripción."""
        try:
            model = self._get_ai_model()

            prompt = f"""Genera un artículo de blog en HTML sobre este audio/podcast.

Transcripción:
{transcript[:4000]}

Tema: {tema}

Requisitos:
- Estructura HTML con etiquetas <p> y <h2>
- Título en <h1>
- Al menos 5 párrafos bien desarrollados
- Resumen del contenido del audio
- Solo devuelve el HTML del artículo"""

            content = model.generate(prompt)

            title_match = re.search(r"<h1>(.*?)</h1>", content, re.DOTALL)
            title = title_match.group(1).strip() if title_match else f"Audio: {tema}"

            slug = slugify(title[:50])

            article = {
                "title": title,
                "title_es": title,
                "content": content,
                "desc": transcript[:500],
                "slug": slug,
                "labels": [tema],
                "source_type": "audio_man",
                "url": f"https://nbes.blog/{slug}",
                "original_url": url,
            }

            return {"article": article, "news_item": article}

        except Exception as e:
            logger.error(f"[AUDIO] Error generando artículo: {e}")
            lines = transcript.split("\n")[:20]
            body = "<h1>Audio Noticia</h1>\n"
            for i, line in enumerate(lines):
                if i % 4 == 0 and i > 0:
                    body += "<h2>Punto clave</h2>\n"
                body += f"<p>{line.strip()}</p>\n"

            return {
                "article": {
                    "title": "Audio Noticia",
                    "title_es": "Audio Noticia",
                    "content": body,
                    "slug": slugify("audio-noticia"),
                    "labels": [tema],
                    "source_type": "audio_man",
                },
                "news_item": {},
            }

    def _generate_tweet(self, article_data: Dict) -> str:
        """Genera tweet desde artículo."""
        title = article_data.get("article", {}).get("title", "Audio Noticia")

        try:
            model = self._get_ai_model()
            prompt = f"Genera un tweet breve sobre este audio: {title[:100]}. Máximo 280 caracteres."
            tweet = model.generate(prompt).strip()
            if len(tweet) > 280:
                tweet = tweet[:277] + "..."
            return tweet
        except Exception:
            pass

        return f"🎙️ {title[:200]}\n\n#Audio #Podcast"

    def _save_outputs(self, article_data: Dict, transcript: str):
        """Guarda los outputs."""
        article = article_data.get("article", {})

        articles_path = DATA_DIR / "generated_audio_articles.json"
        posts_path = DATA_DIR / "generated_audio_posts.json"

        with open(articles_path, "w", encoding="utf-8") as f:
            json.dump([article], f, indent=2, ensure_ascii=False)

        with open(posts_path, "w", encoding="utf-8") as f:
            tweet = self._generate_tweet(article_data)
            json.dump(
                [{"tweet": tweet, "article": article}], f, indent=2, ensure_ascii=False
            )

        logger.info(f"[AUDIO] Archivos guardados en {DATA_DIR}")

    def process_audio_url(self, url: str) -> Dict[str, Any]:
        """Procesa un audio y genera artículo."""
        logger.info(f"[AUDIO] Procesando audio: {url}")

        if check_copyright(url):
            logger.warning(f"[AUDIO] Posible riesgo de copyright: {url}")

        file_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
        audio_path = CACHE_DIR / f"{file_id}.mp3"
        transcript_path = CACHE_DIR / f"{file_id}.txt"

        transcript = self._get_or_create_transcript(url, audio_path, transcript_path)

        article_data = self._generate_article(transcript, url)

        tweet = self._generate_tweet(article_data)

        self._save_outputs(article_data, transcript)

        result = {
            "transcript": transcript,
            "transcript_file": str(transcript_path),
            "article": article_data["article"].get("content", ""),
            "article_file": str(DATA_DIR / "generated_audio_articles.json"),
            "post": tweet,
            "mode": "audio",
        }

        logger.info("[AUDIO] Procesamiento completado")
        return result


def process_audio_url(
    url: str,
    model_provider: str = "openrouter",
    use_ai: bool = True,
    ai_config: dict = None,
) -> Dict[str, Any]:
    """Función principal."""
    processor = AudioToNewsUseCase(
        model_provider=model_provider,
        use_ai=use_ai,
        ai_config=ai_config,
    )
    return processor.process_audio_url(url)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Procesar audio y generar artículo")
    parser.add_argument("url", help="URL del audio")
    parser.add_argument(
        "--model",
        type=str,
        default="openrouter",
        choices=["gemini", "openrouter", "local", "mock"],
        help="Modelo de IA a usar",
    )
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")

    args = parser.parse_args()

    result = process_audio_url(
        url=args.url,
        model_provider=args.model,
        use_ai=not args.local,
    )
    print(f"✅ Procesado: {args.url}")
    print(f"📄 Artículo: {len(result['article'])} caracteres")
    print(f"🐦 Tweet: {result['post'][:100]}...")


if __name__ == "__main__":
    main()
