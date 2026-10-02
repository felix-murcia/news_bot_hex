import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from config.logging_config import get_logger
from src.news.domain.ports import VerifiedNewsRepository, GeneratedPostsRepository, GeneratedArticlesRepository
from src.shared.adapters.ai.agents import ArticleAgent
from src.shared.adapters.translator import translate_text
from src.news.domain.services.template_renderer import TemplateRenderer
from src.shared.adapters.seo_optimizer import (
    slugify as seo_slugify,
    extract_focus_keyphrase,
    generate_meta_description,
    generate_excerpt,
    truncate_seo_title,
    clean_title as seo_clean_title,
)

logger = get_logger("news_bot.usecase.article")

_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "templates"
    / "plantilla_periodico.html"
)


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc or url
    except Exception:
        return url


def _load_template_content() -> Optional[str]:
    """Load template from disk. Returns None if not found."""
    try:
        if _TEMPLATE_PATH.exists():
            return _TEMPLATE_PATH.read_text(encoding="utf-8")
    except Exception:
        pass
    return None




def _limpiar_html(html: str) -> str:
    if not html:
        return html

    # Remove markdown code fences
    html = re.sub(r"```html", "", html)
    html = re.sub(r"```", "", html)

    # Remove markdown bold/italic (**, *, __, _)
    html = re.sub(r"\*\*(.+?)\*\*", r"\1", html)
    html = re.sub(r"\*(.+?)\*", r"\1", html)
    html = re.sub(r"__(.+?)__", r"\1", html)
    html = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", html)

    # Remove markdown links [text](url) → text
    html = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", html)

    # Remove markdown headers (# ## ###)
    html = re.sub(r"^#{1,6}\s+", "", html, flags=re.MULTILINE)

    # Remove <h1> tags
    html = re.sub(r"<h1>.*?</h1>", "", html, flags=re.DOTALL)
    
    # Remove generic 'Título:' prefix at the start of text or within tags
    html = re.sub(r"^(<[^>]+>)*\s*T[íi]tulo:\s*(?:<[/]strong>)?\s*", r"\1", html, flags=re.IGNORECASE).strip()
    html = re.sub(r"(?i)<p>(?:<strong>)?\s*T[íi]tulo:(?:<[/]strong>)?\s*", "<p>", html)

    # Remove <div> tags
    html = re.sub(r"<div.*?>", "", html)
    html = re.sub(r"</div>", "", html)

    # Normalize whitespace
    html = re.sub(r"\n+", "\n", html)
    html = re.sub(r" +", " ", html)

    # Fix HTML entities
    html = re.sub(r"&lt;", "<", html)
    html = re.sub(r"&gt;", ">", html)
    html = re.sub(r"&amp;", "&", html)

    return html.strip()


def _validar_titulo(titulo: str) -> str:
    if not titulo:
        return "Noticia de Última Hora"
    # Clean up AI output prefixes if any
    titulo = re.sub(r"(?i)^T[íi]tulo:\s*", "", titulo).strip()
    if len(titulo) < 10 or "un momento" in titulo.lower():
        return "Noticia de Última Hora"
    return seo_clean_title(titulo)


class ArticleTooShortError(ValueError):
    """El artículo no alcanzó el mínimo de palabras ni regenerando.

    Hereda de ValueError por compatibilidad con quien ya capture ese tipo,
    pero se distingue para no caer al _generate_fallback: un artículo corto
    debe fallar el pipeline, no publicarse truncado.
    """


def _contar_palabras(html: str) -> int:
    """Cuenta palabras del texto visible, ignorando las etiquetas HTML.

    El artículo se mide sobre lo que se publica, no sobre lo que devolvió el
    modelo: contar etiquetas inflaría el resultado y dejaría pasar artículos cortos.
    """
    sin_tags = re.sub(r"<[^>]+>", " ", html or "")
    sin_entities = re.sub(r"&[a-zA-Z]+;|&#\d+;", " ", sin_tags)
    return len([p for p in sin_entities.split() if p.strip()])


class ArticleUseCase:
    """Caso de uso para generar artículos con IA (DIP: inyección de repositorio)."""

    # El prompt exige 800 palabras, pero el modelo las produce cuando quiere:
    # medido con Gemma 4 devuelve 520-620 y finish_reason="stop" — no se queda
    # sin tokens, decide parar antes. Un artículo de 500 palabras no tiene
    # densidad de noticia, así que se mide y se regenera si no llega.
    MIN_WORDS = 800
    MAX_REGENERATIONS = 2

    def __init__(
        self,
        verified_repo: VerifiedNewsRepository,
        generated_posts_repo: GeneratedPostsRepository,
        generated_articles_repo: GeneratedArticlesRepository,
        use_ai: bool = True,
        ai_config: Optional[dict] = None,
        ai_model=None,
        model_provider: str = "gemini",
    ):
        self.verified_repo = verified_repo
        self.generated_posts_repo = generated_posts_repo
        self.generated_articles_repo = generated_articles_repo
        self.use_ai = use_ai
        self.ai_config = ai_config or {}
        self.ai_model = ai_model
        self.model_provider = model_provider
        self._template_renderer = None

    def _get_ai_model(self):
        """Obtiene el modelo de IA (lazy loading)."""
        if self.ai_model is None:
            from src.shared.adapters.ai.ai_factory import get_ai_adapter

            provider = self.model_provider if self.use_ai else "mock"
            self.ai_model = get_ai_adapter(provider, self.ai_config)
            logger.info(f"[ARTICLE] Adapter '{provider}' instanciado")
        return self.ai_model

    def _get_template_renderer(self):
        """Obtiene el renderer de plantillas (lazy loading)."""
        if self._template_renderer is None:
            template_content = _load_template_content()
            if template_content:
                self._template_renderer = TemplateRenderer(template_content)
            else:
                # Fallback: pass-through renderer (no template)
                self._template_renderer = None
        return self._template_renderer

    def _generate_article_body(self, news_item: Dict, mode: str = "news") -> str:
        if self.use_ai:
            return self._generate_with_ai(news_item, mode)
        return self._generate_fallback(news_item)

    def _get_full_content(self, news_item: Dict) -> str:
        """Get full content from verified_news based on URL matching (DIP: usa repositorio inyectado)."""
        try:
            url = news_item.get("url", "")
            # Intenta obtener por URL primaria
            verified = self.verified_repo.get_news_by_url(url)
            if verified:
                return verified.content or verified.desc or ""
            # Nota: Si necesitara búsqueda por original_url, habría que añadir un método al puerto
        except Exception as e:
            logger.warning(f"[ARTICLE] Error getting full content: {e}")
        return ""

    def _generate_with_ai(self, news_item: Dict, mode: str) -> str:
        try:
            model = self._get_ai_model()
            raw_title = news_item.get("title", "")

            try:
                title = news_item.get("title_es") or translate_text(
                    raw_title[:200], target_lang="es"
                )
            except Exception:
                title = raw_title

            tema = news_item.get("tema", "Noticias")

            raw_content = self._get_full_content(news_item)
            if not raw_content:
                raw_content = news_item.get("content", news_item.get("desc", ""))

            # Allow up to 10000 chars of source content so the AI has enough material
            # for a professional 800+ word article
            content_limitado = raw_content[:10000] if raw_content else ""
            try:
                content_es = translate_text(content_limitado, target_lang="es")
            except Exception as e:
                logger.warning(f"[ARTICLE] Error translating: {e}, using original")
                content_es = content_limitado

            keyphrase = extract_focus_keyphrase(title)

            agent = ArticleAgent(model)
            peticion = (
                f"Título: {title}\n"
                f"Tema: {tema}\n"
                f"Palabra clave SEO (incluir 3-5 veces de forma natural): {keyphrase}\n\n"
                f"Contenido informativo:\n{content_es}"
            )

            html = _limpiar_html(agent.generate(topic_or_news=peticion))
            palabras = _contar_palabras(html)
            intentos = 0

            while palabras < self.MIN_WORDS and intentos < self.MAX_REGENERATIONS:
                intentos += 1
                faltan = self.MIN_WORDS - palabras
                logger.warning(
                    f"[ARTICLE] Corto: {palabras} palabras (mínimo {self.MIN_WORDS}). "
                    f"Regenerando {intentos}/{self.MAX_REGENERATIONS}, faltan {faltan}."
                )
                # Se pide explícitamente la longitud: el prompt por sí solo no basta
                # (Gemma devuelve ~550 y finish_reason="stop" sin quedarse sin tokens).
                refuerzo = (
                    f"\n\nIMPORTANTE: el borrador anterior se quedó en {palabras} palabras "
                    f"y necesita al menos {self.MIN_WORDS}. Amplía el desarrollo de los "
                    f"hechos, añade contexto y análisis, y distribúyelo en 14-16 párrafos "
                    f"con 5-6 secciones <h2>. No resumas, no repitas y no añadas etiquetas "
                    f"de estructura."
                )
                html = _limpiar_html(agent.generate(topic_or_news=peticion + refuerzo))
                nuevas = _contar_palabras(html)
                logger.info(f"[ARTICLE] Regeneración {intentos}: {palabras} → {nuevas} palabras")
                palabras = nuevas

            if palabras < self.MIN_WORDS:
                # Fail-fast: publicar un artículo que no llega al estándar es peor
                # que no publicar. El caller decide con el error.
                raise ArticleTooShortError(
                    f"Artículo demasiado corto tras {intentos} regeneraciones: "
                    f"{palabras} palabras, mínimo exigido {self.MIN_WORDS}"
                )

            logger.info(f"[ARTICLE] Generado: {palabras} palabras ({intentos} regeneraciones)")
            return html
        except ArticleTooShortError:
            # No se degrada a fallback: publicar el artículo truncado del
            # extractor sería justo lo que la comprobación evita.
            raise
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
        from config.settings import Settings

        raw_title = news_item.get("title", "Noticia de Última Hora")
        try:
            titulo = news_item.get("title_es") or translate_text(
                raw_title[:200], target_lang="es"
            )
        except Exception:
            titulo = raw_title

        titulo_limpio = re.sub(r"<[^>]+>", "", titulo).strip()
        titulo_limpio = _validar_titulo(titulo_limpio)

        slug = seo_slugify(titulo_limpio)

        first_p = ""
        clean = re.sub(r"<[^>]+>", " ", article_body)
        paragraphs = [p.strip() for p in clean.split("\n") if p.strip()]
        if paragraphs:
            first_p = paragraphs[0]

        meta_description = generate_meta_description(titulo_limpio, first_p)
        seo_title = truncate_seo_title(titulo_limpio)
        focus_keyword = extract_focus_keyphrase(titulo_limpio)

        payload = {
            "title": titulo_limpio,
            "title_es": titulo_limpio,
            "slug": slug,
            "content": article_body,
            "desc": generate_excerpt(first_p),
            "excerpt": generate_excerpt(first_p),
            "meta_description": meta_description,
            "labels": [news_item.get("tema", "Noticias")],
            "source_type": news_item.get("source_type", "news_man"),
            "image_url": news_item.get("image_url", Settings.WP_DEFAULT_IMAGE_URL),
            "image_credit": "NBES",
            "alt_text": titulo_limpio,
            "url": f"{Settings.WP_SITE_URL}/{slug}",
            "original_url": news_item.get("url", ""),
            "seo_title": seo_title,
            "focus_keyword": focus_keyword,
        }

        return payload

    def load_generated_posts(self) -> List[Dict]:
        try:
            return self.generated_posts_repo.load_all()
        except Exception as e:
            logger.error(f"[ARTICLE] Error cargando posts: {e}")
            return []

    def get_current_verified_url(self) -> str:
        try:
            news = self.verified_repo.get_all_news()
            if news:
                return news[0].url
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

            # Check for AI translation or server errors that might have bypassed other checks
            error_patterns = ["Error 500", "Server Error", "That’s an error", "403 Forbidden"]
            for pattern in error_patterns:
                if pattern.lower() in body_html.lower() or pattern.lower() in str(item.get('title', '')).lower():
                    raise RuntimeError(f"Contenido generado inválido, posible página de error devuelta por IA o Traductor: {pattern}")

            payload = self.make_payload(item, body_html)

            # Render with newspaper template
            try:
                renderer = self._get_template_renderer()
                if renderer is None:
                    # No template available, use body as-is
                    logger.info(
                        f"[ARTICLE] Sin plantilla, usando contenido directo: {payload['title']}"
                    )
                else:
                    category = item.get("tema", "Noticias")
                    if category in ("Video", "Política", "Política internacional"):
                        category = "Noticias"
                    category_slug = category.lower().replace(" ", "-")

                    rendered = renderer.render(
                        article_body_html=body_html,
                        title=payload["title"],
                        source_url=item.get("url", ""),
                        category=category,
                        category_slug=category_slug,
                        image_url=payload.get("image_url", ""),
                        slug=payload["slug"],
                        excerpt=payload.get("excerpt", ""),
                    )

                    payload["content"] = rendered["content"]
                    if rendered["image_url"]:
                        payload["image_url"] = rendered["image_url"]

                    logger.info(f"[ARTICLE] ✅ Plantilla aplicada: {payload['title']}")
            except Exception as e:
                logger.warning(f"[ARTICLE] Error aplicando plantilla: {e}")

            generated.append(payload)
            logger.info(f"[ARTICLE] ✅ Artículo generado: {payload.get('title')}")

        if generated:
            try:
                self.generated_articles_repo.save_all(generated)
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
        model_provider: str = "gemini",
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
    model_provider: str = None,
) -> List[Dict]:
    from config.settings import Settings
    from src.shared.adapters.mongo_db import get_database
    from src.news.infrastructure.adapters import MongoVerifiedNewsRepository, MongoGeneratedPostsRepository, MongoGeneratedArticlesRepository

    provider = model_provider or Settings.AI_PROVIDER
    logger.info(f"[ARTICLE] Ejecutando (provider: {provider})")
    db = get_database()
    use_case = ArticleUseCase(
        verified_repo=MongoVerifiedNewsRepository(db),
        generated_posts_repo=MongoGeneratedPostsRepository(db),
        generated_articles_repo=MongoGeneratedArticlesRepository(db),
        use_ai=use_gemini,
        ai_config=ai_config,
        model_provider=provider,
    )
    return use_case.execute(limit=limit, mode=mode)


def main():
    import argparse
    from config.settings import Settings

    parser = argparse.ArgumentParser(description="Generador de artículos con IA")
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")
    parser.add_argument("--limit", type=int, default=1, help="Límite de artículos")
    parser.add_argument(
        "--model",
        type=str,
        default=Settings.AI_PROVIDER,
        choices=Settings.SUPPORTED_AI_PROVIDERS,
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
