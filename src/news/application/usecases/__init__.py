from datetime import datetime

from src.news.domain.entities.verified_article import VerifiedArticle
from src.news.domain.ports import (
    RSSSourceRepository,
    ArticleRepository,
    RSSFetcher,
    VerifiedNewsRepository,
    PublishedUrlsRepository,
    FrozenTermsRepository,
    KeywordsRepository,
    ScoringConfigRepository,
    ContentExtractor,
    FakeNewsModel,
    GeneratedArticlesRepository,
)

# Infrastructure functions used by application layer (acceptable for orchestration)
from src.news.infrastructure.adapters import (
    parse_date_flexible,
    is_today_or_yesterday,
    get_article_date,
    compute_score,
    categorizar_noticia,
    check_breaking_keywords,
    is_valid_score,
    sort_verified_news,
    resumir_noticia,
    deduplicate_by_similarity,
    apply_diversity_penalty,
    extract_frozen_terms,
    apply_frozen_terms_penalty,
)

class FetchRSSNewsUseCase:
    def __init__(
        self,
        source_repo: RSSSourceRepository,
        article_repo: ArticleRepository,
        rss_fetcher: RSSFetcher,
    ):
        self._source_repo = source_repo
        self._article_repo = article_repo
        self._rss_fetcher = rss_fetcher

    def execute(self) -> dict:
        sources = self._source_repo.get_all_sources()
        if not sources:
            return {
                "status": "error",
                "message": "No se encontraron fuentes RSS en MongoDB.",
            }

        all_new_articles = []
        for src in sources:
            url = src.get("url")
            source_name = src.get("source", "Desconocido")
            if not url:
                continue
            articles = self._rss_fetcher.fetch(url, source_name, "RSS")
            recent_articles = []
            for article in articles:
                raw_date = get_article_date(article.to_dict())
                parsed_date = parse_date_flexible(raw_date)
                if parsed_date and is_today_or_yesterday(parsed_date):
                    recent_articles.append(article)
            all_new_articles.extend(recent_articles)

        existing = self._article_repo.get_all_articles()
        seen_urls = {item.url for item in existing if item.url}
        new_unique = [a for a in all_new_articles if a.url not in seen_urls]

        if new_unique:
            self._article_repo.insert_articles(new_unique)

        total = self._article_repo.count_articles()
        return {
            "status": "success",
            "new_articles": len(new_unique),
            "total_articles": total,
        }


class VerifyNewsUseCase:
    def __init__(
        self,
        verified_repo: VerifiedNewsRepository,
        generated_articles_repo: GeneratedArticlesRepository,
        content_extractor: ContentExtractor = None,
    ):
        self._verified_repo = verified_repo
        self._generated_articles_repo = generated_articles_repo
        self._content_extractor = content_extractor

    def execute(self) -> dict:
        from config.settings import Settings

        new_articles = self._generated_articles_repo.load_all()
        if not new_articles:
            return {"status": "error", "message": "No hay artículos en generated_articles"}

        verified_articles = []
        for art in new_articles:
            title = art.get("title", "")
            content = art.get("content", "")
            slug = art.get("slug", "")

            # title_es vacío a propósito: el LLM genera el título en español
            # como <h1> del artículo (paso "Generate Articles") y article.py lo
            # extrae y lo escribe de vuelta en el post. No se traduce por API
            # de Google (ver src/shared/adapters/translator.py).
            title_es = ""

            verified_article = VerifiedArticle(
                title=title,
                desc=content,
                source=art.get("source", "NBES"),
                origin="Noticias Web",
                url=f"{Settings.WP_SITE_URL}/{slug}",
                publishedAt=datetime.now(),
                tema=art.get("tema", "Noticias"),
                resumen=resumir_noticia(title, content),
                score=10,
                model_prediction="real",
                confidence=0.95,
                verification={"verified": True},
                slug=slug,
                content=content,
                labels=art.get("labels", ["Noticias"]),
                image_url=art.get("image_url", ""),
                excerpt=art.get("excerpt", ""),
                seo_title=art.get("seo_title", title),
                focus_keyword=art.get("focus_keyword", ""),
                image_credit=art.get("image_credit", ""),
                is_draft=art.get("is_draft", False),
                source_url=art.get("source_url", f"{Settings.WP_SITE_URL}/{slug}"),
                alt_text=art.get("alt_text", title),
                source_type="news_man",
                original_url=art.get("original_url", ""),
                title_es=title_es,
            )
            verified_articles.append(verified_article)

        self._verified_repo.delete_all_news()
        self._verified_repo.insert_news(verified_articles)

        return {
            "status": "success",
            "articles": len(verified_articles),
            "saved": True,
        }


from .full_verify_usecase import FullVerifyNewsUseCase
