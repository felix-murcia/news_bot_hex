import os
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
VERIFIED_PATH = DATA_DIR / "verified_news.json"
OUTPUT_PATH = DATA_DIR / "generated_articles.json"
TEMPLATE_NAME = "plantilla_periodico.html"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc or url
    except:
        return url


def abort(reason: str):
    logger.error(f"ERROR: {reason}")
    raise RuntimeError(reason)


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def _limpiar_html(html: str) -> str:
    if not html:
        return html

    html = re.sub(r"```html", "", html)
    html = re.sub(r"```", "", html)
    html = re.sub(r"`", "", html)

    html = re.sub(r"<h1>.*?</h1>", "", html, flags=re.DOTALL)

    html = re.sub(r"<div.*?>", "", html)
    html = re.sub(r"</div>", "", html)

    html = re.sub(r"\n+", "\n", html)

    html = re.sub(r" +", " ", html)

    html = re.sub(r"&lt;", "<", html)
    html = re.sub(r"&gt;", ">", html)
    html = re.sub(r"&amp;", "&", html)

    return html.strip()


def _validar_titulo(titulo: str) -> str:
    if not titulo or len(titulo) < 5:
        return "Noticia de Última Hora"
    titulo = titulo.strip()
    if (
        not titulo.endswith(".")
        and not titulo.endswith("!")
        and not titulo.endswith("?")
    ):
        titulo += "."
    return titulo


class ArticleUseCase:
    """Caso de uso para generar artículos con IA."""

    def __init__(
        self,
        use_ai: bool = True,
        ai_config: Optional[dict] = None,
        ai_model=None,
        model_provider: str = "openrouter",
    ):
        self.use_ai = use_ai
        self.ai_config = ai_config or {}
        self.ai_model = ai_model
        self.model_provider = model_provider

    def _get_ai_model(self):
        """Obtiene el modelo de IA (lazy loading)."""
        if self.ai_model is None:
            from src.shared.adapters.ai.ai_factory import get_ai_adapter

            provider = self.model_provider if self.use_ai else "mock"
            self.ai_model = get_ai_adapter(provider, self.ai_config)
            logger.info(f"[ARTICLE] Adapter '{provider}' instanciado")
        return self.ai_model

    def _generate_article_body(self, news_item: Dict, mode: str = "news") -> str:
        if self.use_ai:
            return self._generate_with_ai(news_item, mode)
        return self._generate_fallback(news_item)

    def _get_full_content(self, news_item: Dict) -> str:
        """Get full content from verified_news based on URL matching."""
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()

            url = news_item.get("url", "")
            verified = db["verified_news"].find_one({"url": url})
            if verified:
                return verified.get("content") or verified.get("desc", "")

            verified = db["verified_news"].find_one({"original_url": url})
            if verified:
                return verified.get("content") or verified.get("desc", "")
        except Exception as e:
            logger.warning(f"[ARTICLE] Error getting full content: {e}")
        return ""

    def _generate_with_ai(self, news_item: Dict, mode: str) -> str:
        try:
            model = self._get_ai_model()
            raw_title = news_item.get("title", "")
            try:
                from src.shared.adapters.translator import translate_text

                title = news_item.get("title_es") or translate_text(
                    raw_title[:200], target_lang="es"
                )
            except Exception:
                title = raw_title

            tema = news_item.get("tema", "Noticias")

            raw_content = self._get_full_content(news_item)
            if not raw_content:
                raw_content = news_item.get("content", news_item.get("desc", ""))

            from src.shared.adapters.translator import translate_text

            content_limitado = raw_content[:3500] if raw_content else ""
            try:
                content_es = translate_text(content_limitado, target_lang="es")
            except Exception as e:
                logger.warning(f"[ARTICLE] Error translating: {e}, using original")
                content_es = content_limitado

            prompt = f"""Genera un artículo de blog en HTML en ESPAÑOL sobre:

Título (en español): {title}
Tema: {tema}
Contenido: {content_es}

Requisitos:
- Escribe TODO el artículo en español
- Estructura HTML con etiquetas <p> y <h2>
- Al menos 5 párrafos bien desarrollados
- Título en <h1>
- Solo devuelve el HTML del artículo"""

            result = model.generate(prompt)
            return _limpiar_html(result)
        except Exception as e:
            logger.error(f"[ARTICLE] Error generando con IA: {e}")
            return self._generate_fallback(news_item)

    def _generate_fallback(self, news_item: Dict) -> str:
        title = news_item.get("title", "Noticia")
        content = news_item.get("content", news_item.get("desc", ""))

        lines = content.split("\n")[:15]
        body = f"<h1>{title}</h1>\n"

        for i, line in enumerate(lines):
            if line.strip():
                if i % 4 == 0 and i > 0:
                    body += f"<h2>Punto clave {i // 4}</h2>\n"
                body += f"<p>{line.strip()}</p>\n"

        return body

    def make_payload(self, news_item: Dict, article_body: str) -> Dict:
        raw_title = news_item.get("title", "Noticia de Última Hora")
        try:
            from src.shared.adapters.translator import translate_text

            titulo = news_item.get("title_es") or translate_text(
                raw_title[:200], target_lang="es"
            )
        except Exception:
            titulo = raw_title

        titulo_limpio = re.sub(r"<[^>]+>", "", titulo).strip()
        titulo_limpio = _validar_titulo(titulo_limpio)

        slug = slugify(titulo_limpio[:50])

        first_p = ""
        clean = re.sub(r"<[^>]+>", " ", article_body)
        paragraphs = [p.strip() for p in clean.split("\n") if p.strip()]
        if paragraphs:
            first_p = paragraphs[0][:160]

        payload = {
            "title": titulo_limpio,
            "title_es": titulo_limpio,
            "slug": slug,
            "content": article_body,
            "desc": first_p,
            "excerpt": first_p,
            "labels": [news_item.get("tema", "Noticias")],
            "source_type": news_item.get("source_type", "news_man"),
            "image_url": news_item.get("image_url", "https://api.nbes.blog/image-310/"),
            "image_credit": "NBES",
            "alt_text": titulo_limpio,
            "url": f"https://nbes.blog/{slug}",
            "original_url": news_item.get("url", ""),
        }

        return payload

    def load_generated_posts(self) -> List[Dict]:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_posts"]
            posts = list(coll.find({}))
            for p in posts:
                p.pop("_id", None)
            return posts
        except Exception as e:
            logger.error(f"[ARTICLE] Error cargando posts: {e}")
            return []

    def get_current_verified_url(self) -> str:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["verified_news"]
            news = list(coll.find({}))
            if news:
                return news[0].get("url", "")
        except Exception as e:
            logger.error(f"[ARTICLE] Error getting verified URL: {e}")
        return ""

    def execute(self, limit: int = 1, mode: str = "news") -> List[Dict]:
        posts = self.load_generated_posts()
        if not posts:
            logger.warning("[ARTICLE] No hay posts para procesar")
            return []

        current_url = self.get_current_verified_url()
        if not current_url:
            logger.warning("[ARTICLE] No hay URL verificada")
            return []

        aligned_posts = [
            p for p in posts if (p.get("url") or "").strip() == current_url
        ]
        if not aligned_posts:
            logger.warning("[ARTICLE] No hay posts que coincidan con la URL verificada")
            return []

        to_process = aligned_posts[:limit] if limit else aligned_posts[:1]
        generated = []

        for item in to_process:
            logger.info(f"[ARTICLE] Procesando: {item.get('title', 'Sin título')}")

            body_html = self._generate_article_body(item, mode)

            if not body_html or len(body_html) < 100:
                logger.warning(f"[ARTICLE] Artículo inválido para: {item.get('title')}")
                continue

            payload = self.make_payload(item, body_html)
            generated.append(payload)
            logger.info(f"[ARTICLE] ✅ Artículo generado: {payload.get('title')}")

        if generated:
            try:
                from src.shared.adapters.mongo_db import get_database

                db = get_database()
                coll = db["generated_articles"]
                coll.delete_many({})
                coll.insert_many(generated)
                logger.info(
                    f"[ARTICLE] Guardados {len(generated)} artículos en MongoDB"
                )
            except Exception as e:
                logger.error(f"[ARTICLE] Error guardando: {e}")

        return generated


class ArticleGeminiUseCase(ArticleUseCase):
    """Legacy compatibility wrapper."""

    def __init__(
        self,
        use_gemini: bool = True,
        gemini_config: Optional[dict] = None,
        ai_model=None,
        model_provider: str = "openrouter",
        **kwargs,
    ):
        super().__init__(
            use_ai=use_gemini,
            ai_config=gemini_config,
            ai_model=ai_model,
            model_provider=model_provider,
            **kwargs,
        )


def run(
    llm=None,
    limit: int = 1,
    use_gemini: bool = True,
    ai_config: Optional[dict] = None,
    mode: str = "news",
    model_provider: str = "openrouter",
) -> List[Dict]:
    logger.info(f"[ARTICLE] Ejecutando (provider: {model_provider})")
    use_case = ArticleUseCase(
        use_ai=use_gemini,
        ai_config=ai_config,
        model_provider=model_provider,
    )
    return use_case.execute(limit=limit, mode=mode)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generador de artículos con IA")
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")
    parser.add_argument("--limit", type=int, default=1, help="Límite de artículos")
    parser.add_argument(
        "--model",
        type=str,
        default="openrouter",
        choices=["gemini", "openrouter", "local", "mock"],
        help="Modelo de IA a usar",
    )

    args = parser.parse_args()

    results = run(
        limit=args.limit, use_gemini=not args.local, model_provider=args.model
    )

    if results:
        print(f"✅ {len(results)} artículo(s) generado(s)")
    else:
        print("⚠️ No se generaron artículos")


if __name__ == "__main__":
    main()
