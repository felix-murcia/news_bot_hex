import os
import logging
import json
import re
from pathlib import Path
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("audio_bot")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
AUDIO_ARTICLES_PATH = DATA_DIR / "generated_audio_articles.json"
AUDIO_POSTS_PATH = DATA_DIR / "generated_audio_posts.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def limpiar(texto: str) -> str:
    if not texto:
        return ""
    return str(texto).strip().strip("*").strip('"').strip()


class ArticleFromAudioUseCase:
    """Caso de uso para generar artículo desde transcripción de audio."""

    def __init__(self, use_gemini: bool = True, gemini_config: dict = None):
        self.use_gemini = use_gemini
        self.gemini_config = gemini_config or {}

    def _generate_with_gemini(
        self, transcript: str, url: str, tema: str
    ) -> Dict[str, Any]:
        """Genera artículo usando Gemini."""
        try:
            # from src.shared.adapters.gemini_client import get_gemini_client
            from src.shared.adapters.openrouter_client import get_openrouter_client

            client = get_openrouter_client(self.gemini_config)

            prompt = """Genera un artículo de blog en HTML sobre este audio/podcast.

Transcripción:
{}

Tema: {}

Requisitos:
- Estructura HTML con etiquetas <p> y <h2>
- Título en <h1>
- Al menos 5 párrafos bien desarrollados
- Solo devuelve el HTML del artículo""".format(transcript[:4000], tema)

            content = client.generate(prompt)

            title_match = re.search(r"<h1>(.*?)</h1>", content, re.DOTALL)
            title = title_match.group(1).strip() if title_match else f"Audio: {tema}"

            return self._build_article_response(content, title, url, tema, "gemini")

        except Exception as e:
            logger.error(f"[ARTICLE_AUDIO] Error con Gemini: {e}")
            return self._generate_fallback(transcript, url, tema)

    def _generate_fallback(
        self, transcript: str, url: str, tema: str
    ) -> Dict[str, Any]:
        """Genera artículo sin Gemini (fallback)."""
        lines = transcript.split("\n")[:30]
        body = f"<h1>Audio sobre {tema}</h1>\n"

        for i, line in enumerate(lines):
            if i % 5 == 0 and i > 0:
                body += "<h2>Punto clave</h2>\n"
            if line.strip():
                body += f"<p>{line.strip()}</p>\n"

        title = f"Audio sobre {tema}"
        return self._build_article_response(body, title, url, tema, "local")

    def _build_article_response(
        self, content: str, title: str, url: str, tema: str, mode: str
    ) -> Dict[str, Any]:
        """Construye la respuesta del artículo."""
        slug = slugify(title[:50])
        content_clean = re.sub(r"<[^>]+>", " ", content)
        first_p = content_clean.split("\n")[0][:160] if content_clean else ""

        article = {
            "title": title,
            "title_es": title,
            "slug": slug,
            "content": content,
            "desc": first_p,
            "excerpt": first_p,
            "labels": [tema],
            "source_type": "audio_man",
            "image_url": "https://api.nbes.blog/image-310/",
            "image_credit": "NBES",
            "alt_text": title,
            "url": f"https://nbes.blog/{slug}",
            "original_url": url,
        }

        tweet = f"🎙️ {title[:200]}\n\n#{tema.replace(' ', '')}"
        if url:
            tweet = f"{tweet}\n{url}"
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."

        parrafos = content.count("<p>")
        subtitulos = content.count("<h2>")

        post = {
            "tweet": tweet,
            "title": title,
            "url": url,
            "source": "audio",
            "source_type": "audio_man",
            "tema": tema,
            "image_url": article["image_url"],
        }

        self._save_outputs(article, post)

        return {
            "article": article,
            "post": post,
            "news_item": article,
            "mode": mode,
            "stats": {
                "parrafos": parrafos,
                "subtitulos": subtitulos,
                "longitud_caracteres": len(content),
            },
        }

    def _save_outputs(self, article: Dict, post: Dict):
        """Guarda los outputs en archivos."""
        with open(AUDIO_ARTICLES_PATH, "w", encoding="utf-8") as f:
            json.dump([article], f, indent=2, ensure_ascii=False)

        with open(AUDIO_POSTS_PATH, "w", encoding="utf-8") as f:
            json.dump([post], f, indent=2, ensure_ascii=False)

        logger.info(f"[ARTICLE_AUDIO] Archivos guardados en {DATA_DIR}")

    def execute(
        self, transcript: str, url: str = "", tema: str = "Audios"
    ) -> Dict[str, Any]:
        """Ejecuta la generación de artículo."""
        logger.info(f"[ARTICLE_AUDIO] Generando artículo para tema: {tema}")

        if self.use_gemini:
            return self._generate_with_gemini(transcript, url, tema)
        return self._generate_fallback(transcript, url, tema)


def run_from_audio(
    transcript: str,
    url: str = "",
    tema: str = "Audios",
    use_gemini: bool = True,
    llm: Any = None,
    gemini_config: Dict = None,
) -> Dict[str, Any]:
    """Función principal."""
    logger.info(f"[ARTICLE_AUDIO] Ejecutando (Gemini: {use_gemini})")
    use_case = ArticleFromAudioUseCase(
        use_gemini=use_gemini, gemini_config=gemini_config
    )
    return use_case.execute(transcript, url, tema)


def main():
    import argparse
    import time

    parser = argparse.ArgumentParser(
        description="Generar artículo desde transcripción de audio"
    )
    parser.add_argument(
        "--transcript", type=str, required=True, help="Archivo con transcripción"
    )
    parser.add_argument("--url", type=str, default="", help="URL del audio")
    parser.add_argument("--tema", type=str, default="Audios", help="Tema del artículo")
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")

    args = parser.parse_args()

    if os.path.exists(args.transcript):
        with open(args.transcript, "r", encoding="utf-8") as f:
            transcript = f.read()
    else:
        transcript = args.transcript

    start_time = time.time()

    try:
        results = run_from_audio(
            transcript=transcript,
            url=args.url,
            tema=args.tema,
            use_gemini=not args.local,
        )

        elapsed = time.time() - start_time

        print(f"\n✅ Artículo desde audio generado en {elapsed:.1f}s")
        print(f"📰 Título: {results['article']['title']}")
        print(f"📊 Modo: {results.get('mode', 'desconocido')}")
        print(
            f"📈 Estructura: {results['stats']['parrafos']}p/{results['stats']['subtitulos']}h2"
        )
        print(f"🔗 Guardado en: {AUDIO_ARTICLES_PATH}")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
