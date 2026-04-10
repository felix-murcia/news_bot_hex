import os
import logging
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Any

from config.settings import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("video_bot")

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
        llm_provider: str = "openrouter",
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
        """Genera artículo usando el cliente LLM configurado."""
        from src.shared.adapters.translator import translate_text

        transcerpt_es = translate_text(transcript[:3000], target_lang="es")

        prompt = f"""Genera un artículo de blog en HTML en ESPAÑOL sobre este video.

Transcripción (traducida):
{transcerpt_es}

Tema: {tema}

Requisitos:
- Escribe TODO el artículo en español
- Estructura HTML con etiquetas <p> y <h2>
- Título en <h1>
- Al menos 5 párrafos bien desarrollados
- Solo devuelve el HTML del artículo"""

        content = self._get_ai_model().generate(prompt)

        title_match = re.search(r"<h1>(.*?)</h1>", content, re.DOTALL)
        title = title_match.group(1).strip() if title_match else f"Video: {tema}"

        return self._build_article_response(content, title, url, tema)

    def _build_article_response(
        self, content: str, title: str, url: str, tema: str
    ) -> Dict[str, Any]:
        """Construye la respuesta del artículo."""
        slug = slugify(title[:50])

        content_clean = content
        content_clean = re.sub(r"^```html\s*", "", content_clean, flags=re.MULTILINE)
        content_clean = re.sub(r"^```\s*$", "", content_clean, flags=re.MULTILINE)
        content_clean = content_clean.strip()

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
        """Genera tweet profesional."""
        clean = re.sub(r"<[^>]+>", " ", content)
        lines = [l.strip() for l in clean.split("\n") if l.strip()]
        context = lines[0][:300] if lines else title

        tweet_prompt = f"""# ROLE: EDITOR JEFE DE GEOPOLÍTICA – THE ECONOMIST
Actúa como editor senior de la sección de geopolítica de The Economist. Tu función es transformar contenido en un tweet periodístico profesional, preciso y objetivo.

INPUT
Título: {title}
Tema: {tema}
Contenido: {context[:200]}

HARD RULES (OBLIGATORIAS)
- Estilo escrito periodístico (The Economist, FT, El País).
- Objetividad total: no opiniones, no especulación, no sensacionalismo.
- Tercera persona, tono formal, sin coloquialismos.
- No pongas "Video sobre..." ni "Este video trata de..."

TWEET FORMAT
[L1] Hecho principal conciso y relevante
[L2] Contexto, impacto o consecuencia
[HASHTAGS] 2–3 hashtags específicos del tema

PROHIBIDO
- "Descubre los detalles"
- "Link a la noticia"
- "Video sobre..."
- "Este video trata de..."

TASK
Genera EXACTAMENTE UN tweet periodístico profesional en español.
Máximo 280 caracteres.
Empieza directamente con el tweet.

TWEET:"""

        tweet = self.llm_client.generate(tweet_prompt)
        if not tweet:
            raise RuntimeError("Tweet generation failed: empty response from LLM")

        tweet = tweet.strip()[:280]

        if "Video sobre" in tweet or "este video" in tweet.lower():
            raise ValueError(
                "Tweet generation failed: model produced forbidden pattern"
            )

        tweet = re.sub(r"\[HASHTAGS\]", "", tweet, flags=re.IGNORECASE)
        tweet = re.sub(r"^Hashtags:.*$", "", tweet, flags=re.MULTILINE)
        tweet = re.sub(r"^\s*#\w+\s*$", "", tweet, flags=re.MULTILINE)
        tweet = tweet.strip()

        if len(tweet) > 280:
            tweet = tweet[:277] + "..."

        return tweet


def run_from_video(
    transcript: str,
    url: str = "",
    tema: str = "Videos",
    # llm_provider: str = "gemini",
    llm_provider: str = "openrouter",
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
        default="openrouter",
        choices=["gemini", "openrouter", "local", "mock"],
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
