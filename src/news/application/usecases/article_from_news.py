import os
import re
import traceback
from typing import Any, Callable, Dict

import logging
from src.shared.domain.services.ai_providers import AiProviders

logger = logging.getLogger(__name__)
def limpiar(texto: str) -> str:
    if not texto:
        return ""
    return str(texto).strip().strip("*").strip('"').strip()


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
        ai_providers: AiProviders,
        use_ai: bool = True,
        model_provider: str = "gemini",
        ai_model=None,
        wp_site_url: str = "",
        wp_default_image_url: str = "",
        social_truncator: Callable[..., str] = None,
        post_editor: Callable[..., str] = None,
        translator: Callable[[str, str], str] = None,
    ):
        if social_truncator is None or post_editor is None:
            raise ValueError("social_truncator y post_editor son requeridos")
        if translator is None:
            raise ValueError("translator es requerido")
        if ai_providers is None:
            raise ValueError("ai_providers es requerido")
        self.use_ai = use_ai
        self.model_provider = model_provider
        self.ai_model = ai_model
        self._ai_providers = ai_providers
        self._wp_site_url = wp_site_url
        self._wp_default_image_url = wp_default_image_url
        self._social_truncator = social_truncator
        self._post_editor = post_editor
        self._translator = translator

    def _get_ai_model(self):
        """Obtiene el modelo de IA (lazy loading)."""
        if self.ai_model is None:
            provider = self.model_provider if self.use_ai else "mock"
            self.ai_model = self._ai_providers.adapter_factory(provider)
            logger.info(f"[ARTICLE_NEWS] Adapter '{provider}' instanciado")
        return self.ai_model

    def execute(
        self, content: str, url: str = "", tema: str = "Noticias"
    ) -> Dict[str, Any]:

        logger.info(
            f"[ARTICLE_NEWS] Iniciando generación desde noticia para tema: {tema}"
        )

        content_es = self._translator(content, "es")
        logger.info(f"[ARTICLE_NEWS] Contenido traducido: {len(content_es)} caracteres")

        resumen = limpiar(content_es[:500])

        news_item = {
            "resumen": resumen,
            "source_url": url,
            "url": self._wp_site_url,
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

        # Aplicar post-edición automática al artículo
        article_body = self._post_editor(article_body)

        parrafos = article_body.count("<p>")
        subtitulos = article_body.count("<h2>")
        logger.info(
            f"[ARTICLE_NEWS] Artículo generado: {parrafos} párrafos, {subtitulos} subtítulos"
        )

        # Extract title from article_body if it contains <h1>, then remove the tag if found.
        extracted_title = self._extract_title_from_html(article_body)
        
        # Robust Validation: if the title is too short or clearly AI conversational garbage, fallback.
        if not extracted_title or len(extracted_title) < 10 or "un momento" in extracted_title.lower():
            title = news_item.get("title", "Noticia de Última Hora")
        else:
            title = extracted_title
            
        # Remove <h1> tag from body so it's not rendered in WP
        article_body = re.sub(r"<h1>.*?</h1>", "", article_body, flags=re.DOTALL)
        # Remove any leading 'Título:' that the AI might have outputted instead of in an <h1>
        article_body = re.sub(r"^(<[^>]+>)*\s*T[íi]tulo:\s*", r"\1", article_body, flags=re.IGNORECASE).strip()

        payload = {
            "title": title,
            "title_es": title,
            "content": article_body,
            "desc": content_es[:500],
            "slug": self._generate_slug(title),
            "labels": [tema],
            "source_type": "news_man",
            "image_url": self._wp_default_image_url,
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

        # Aplicar post-edición automática al tweet
        tweet_text = self._post_editor(tweet_text)

        post = build_article_post(news_item, payload, tweet_text, "news_man")

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
        url = news_item.get("url", self._wp_site_url)
        tweet = f"📰 {title[:200]}\n\nLeer más: {url}"

        tweet = self._social_truncator(tweet)
        return tweet

    def _extract_title_from_html(self, html: str) -> str:
        """Extract title from HTML <h1> tag if present, stripping generic 'Titulo' prefixes."""
        match = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean "Título: " prefix if present
            title = re.sub(r"(?i)^T[íi]tulo:\s*", "", title).strip()
            if title:
                return title
        return ""

    def _generate_slug(self, title: str) -> str:
        slug = title.lower()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_-]+", "-", slug)
        slug = slug.strip("-")
        return slug[:100]

def run_from_news(
    content: str,
    url: str = "",
    tema: str = "Noticias",
    use_gemini: bool = True,
    model_provider: str = "gemini",
    wp_site_url: str = "",
    wp_default_image_url: str = "",
    *,
    ai_providers: AiProviders,
    social_truncator: Callable[..., str],
    post_editor: Callable[..., str],
    translator: Callable[[str, str], str],
) -> Dict[str, Any]:
    """Función de compatibilidad para pipeline existente."""
    logger.info(
        f"[ARTICLE_NEWS] Ejecutando pipeline para noticias (provider: {model_provider})"
    )
    use_case = ArticleFromNewsUseCase(
        ai_providers=ai_providers,
        use_ai=use_gemini,
        model_provider=model_provider,
        wp_site_url=wp_site_url,
        wp_default_image_url=wp_default_image_url,
        social_truncator=social_truncator,
        post_editor=post_editor,
        translator=translator,
    )
    return use_case.execute(content, url, tema)


def main():
    import argparse
    from config.settings import Settings

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
        default=Settings.AI_PROVIDER,
        choices=Settings.SUPPORTED_AI_PROVIDERS,
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
        social_truncator = __import__(
            "src.shared.adapters.social_post_adapter", fromlist=["truncate_social_post"]
        ).truncate_social_post
        post_editor = __import__(
            "src.shared.adapters.content_post_editor", fromlist=["post_edit_content"]
        ).post_edit_content
        from src.shared.adapters.translator import translate_text
        from src.shared.infrastructure.composition_root import (  # TODO B11c (main/argparse)
            create_ai_providers,
        )

        results = run_from_news(
            content=content,
            url=args.url,
            tema=args.tema,
            use_gemini=not args.local,
            model_provider=args.model,
            wp_site_url=Settings.WP_SITE_URL,
            wp_default_image_url=Settings.WP_DEFAULT_IMAGE_URL,
            ai_providers=create_ai_providers(),
            social_truncator=social_truncator,
            post_editor=post_editor,
            translator=translate_text,
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
        traceback.print_exc()


if __name__ == "__main__":
    main()
