import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from config.settings import Settings
from src.shared.adapters.translator import translate_text
from src.news.infrastructure.adapters import JinaContentExtractor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")

DATA_DIR = Settings.DATA_DIR
CACHE_DIR = Settings.CACHE_DIR
NEWS_ARTICLES_PATH = DATA_DIR / "generated_news_articles.json"
NEWS_POSTS_PATH = DATA_DIR / "generated_news_posts.json"

CACHE_DIR.mkdir(parents=True, exist_ok=True)


def limpiar(texto: str) -> str:
    if not texto:
        return ""
    return str(texto).strip().strip("*").strip('"').strip()


def save_payloads(payload: Dict, post: Dict):
    NEWS_ARTICLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(NEWS_ARTICLES_PATH, "w", encoding="utf-8") as f:
        json.dump([payload], f, indent=2, ensure_ascii=False)
    with open(NEWS_POSTS_PATH, "w", encoding="utf-8") as f:
        json.dump([post], f, indent=2, ensure_ascii=False)
    logger.info(f"[ARTICLE_NEWS] Archivos guardados en {DATA_DIR}")


def build_article_post(
    news_item: Dict, payload: Dict, tweet_text: str, source_type: str = "news_man"
) -> Dict:
    return {
        "article": payload,
        "tweet": tweet_text,
        "news_item": news_item,
        "source_type": source_type,
    }


class ArticleFromNewsUseCase:
    """Caso de uso para generar artículo desde noticia."""

    def __init__(
        self,
        use_ai: bool = True,
        model_provider: str = "openrouter",
        ai_config: Optional[dict] = None,
        ai_model=None,
    ):
        self.use_ai = use_ai
        self.model_provider = model_provider
        self.ai_config = ai_config or {}
        self.ai_model = ai_model
        self.content_extractor = JinaContentExtractor()

    def _get_ai_model(self):
        """Obtiene el modelo de IA (lazy loading)."""
        if self.ai_model is None:
            from src.shared.adapters.ai.ai_factory import get_ai_adapter

            provider = self.model_provider if self.use_ai else "mock"
            self.ai_model = get_ai_adapter(provider, self.ai_config)
            logger.info(f"[ARTICLE_NEWS] Adapter '{provider}' instanciado")
        return self.ai_model

    def execute(
        self, content: str, url: str = "", tema: str = "Noticias"
    ) -> Dict[str, Any]:
        logger.info(
            f"[ARTICLE_NEWS] Iniciando generación desde noticia para tema: {tema}"
        )

        self._clean_previous_files()

        content_es = translate_text(content, "es")
        logger.info(f"[ARTICLE_NEWS] Contenido traducido: {len(content_es)} caracteres")

        resumen = limpiar(content_es[:500])

        news_item = {
            "resumen": resumen,
            "source_url": url,
            "url": Settings.WP_SITE_URL,
            "source": "web",
            "source_type": "news_man",
            "tema": tema,
            "is_draft": False,
            "content": content_es,
            "original_url": url,
        }

        article_body = self._generate_article_body(content_es, news_item)

        if not article_body or article_body.strip() == "":
            logger.error("[ARTICLE_NEWS] No se generó contenido para el artículo")
            raise RuntimeError("No se pudo generar el artículo desde noticia")

        parrafos = article_body.count("<p>")
        subtitulos = article_body.count("<h2>")
        logger.info(
            f"[ARTICLE_NEWS] Artículo generado: {parrafos} párrafos, {subtitulos} subtítulos"
        )

        payload = {
            "title": news_item.get("title", "Noticia de Última Hora"),
            "title_es": news_item.get(
                "title_es", news_item.get("title", "Noticia de Última Hora")
            ),
            "content": article_body,
            "desc": content_es[:500],
            "slug": self._generate_slug(news_item.get("title", "noticia")),
            "labels": [tema],
            "source_type": "news_man",
            "image_url": "https://api.nbes.blog/image-310/",
            "image_credit": "NBES",
            "alt_text": "Logo NBES",
            "original_url": url,
        }

        news_item["title"] = payload.get("title")
        news_item["title_es"] = payload.get("title_es")
        news_item["image_url"] = payload.get("image_url")
        news_item["image_credit"] = payload.get("image_credit")

        tweet_text = self._generate_tweet(news_item)
        logger.info(f"[ARTICLE_NEWS] Tweet generado: {tweet_text[:100]}...")

        post = build_article_post(news_item, payload, tweet_text, "news_man")
        save_payloads(payload, post)

        return {
            "article": payload,
            "post": post,
            "news_item": news_item,
            "mode": self.model_provider if self.use_ai else "local",
            "stats": {
                "parrafos": parrafos,
                "subtitulos": subtitulos,
                "longitud_caracteres": len(article_body),
            },
        }

    def _generate_article_body(self, content: str, news_item: Dict) -> str:
        if self.use_ai:
            return self._generate_with_ai(content, news_item)
        return self._generate_with_local(content, news_item)

    def _generate_with_ai(self, content: str, news_item: Dict) -> str:
        try:
            model = self._get_ai_model()
            prompt = self._build_article_prompt(content, news_item)
            result = model.generate(prompt)
            return self._parse_article_response(result)
        except Exception as e:
            logger.error(f"[ARTICLE_NEWS] Error generando con IA: {e}")
            return self._generate_fallback(content, news_item)

    def _generate_with_local(self, content: str, news_item: Dict) -> str:
        logger.info("[ARTICLE_NEWS] Usando generación local (fallback)")
        return self._generate_fallback(content, news_item)

    def _generate_fallback(self, content: str, news_item: Dict) -> str:
        lines = content.split("\n")[:20]
        body = ""
        for i, line in enumerate(lines):
            if i % 3 == 0 and i > 0:
                body += f"<h2>Información adicional</h2>\n"
            body += f"<p>{line.strip()}</p>\n"
        return body

    def _build_article_prompt(self, content: str, news_item: Dict) -> str:
        tema = news_item.get("tema", "Noticias")
        return f"""Genera un artículo de blog en HTML sobre la siguiente noticia.

Tema: {tema}
Contenido:
{content[:3000]}

Requisitos:
- Estructura HTML con etiquetas <p> y <h2>
- Título en <h1>
- Al menos 5 párrafos
- Artículo completo y bien estructurado
- Solo devuelve el HTML del artículo, sin markdown"""

    def _parse_article_response(self, response: str) -> str:
        response = response.strip()
        if response.startswith("```html"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        return response.strip()

    def _generate_tweet(self, news_item: Dict) -> str:
        title = news_item.get("title", "Nueva noticia")
        url = news_item.get("url", "https://nbes.blog")
        tema = news_item.get("tema", "Noticias")
        tweet = f"📰 {title[:200]}\n\nLeer más: {url}"
        if len(tweet) > 280:
            tweet = f"📰 {title[:200]}... {url}"
        return tweet

    def _generate_slug(self, title: str) -> str:
        import re

        slug = title.lower()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_-]+", "-", slug)
        slug = slug.strip("-")
        return slug[:100]

    def _clean_previous_files(self):
        for file_path in [NEWS_ARTICLES_PATH, NEWS_POSTS_PATH]:
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(
                        f"[ARTICLE_NEWS] Archivo anterior eliminado: {file_path.name}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[ARTICLE_NEWS] No se pudo eliminar {file_path.name}: {e}"
                    )


def run_from_news(
    content: str,
    url: str = "",
    tema: str = "Noticias",
    use_gemini: bool = True,
    model_provider: str = "openrouter",
    ai_config: Optional[dict] = None,
) -> Dict[str, Any]:
    """Función de compatibilidad para pipeline existente."""
    logger.info(
        f"[ARTICLE_NEWS] Ejecutando pipeline para noticias (provider: {model_provider})"
    )
    use_case = ArticleFromNewsUseCase(
        use_ai=use_gemini,
        model_provider=model_provider,
        ai_config=ai_config,
    )
    return use_case.execute(content, url, tema)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generar artículo desde contenido de noticia"
    )
    parser.add_argument(
        "--content",
        type=str,
        required=True,
        help="Archivo con contenido o texto directo",
    )
    parser.add_argument("--url", type=str, default="", help="URL de la noticia")
    parser.add_argument(
        "--tema", type=str, default="Noticias", help="Tema del artículo"
    )
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")
    parser.add_argument(
        "--model",
        type=str,
        default="openrouter",
        choices=["gemini", "openrouter", "local", "mock"],
        help="Modelo de IA a usar",
    )

    args = parser.parse_args()

    if os.path.exists(args.content):
        with open(args.content, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = args.content

    import time

    start_time = time.time()

    try:
        results = run_from_news(
            content=content,
            url=args.url,
            tema=args.tema,
            use_gemini=not args.local,
            model_provider=args.model,
        )
        elapsed = time.time() - start_time

        print(f"\n✅ Artículo desde noticia generado en {elapsed:.1f}s")
        print(f"📰 Título: {results['article']['title']}")
        print(f"📊 Modo: {results.get('mode', 'desconocido')}")
        print(
            f"📈 Estructura: {results['stats']['parrafos']}p/{results['stats']['subtitulos']}h2"
        )
        print(f"🔗 Guardado en: {NEWS_ARTICLES_PATH}")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
