import json
from pathlib import Path
from typing import List
from datetime import datetime
from src.news.domain.entities.article import Article
from src.news.domain.entities.verified_article import VerifiedArticle
from src.news.domain.ports import (
    RSSSourceRepository,
    ArticleRepository,
    RSSFetcher,
    VerifiedNewsRepository,
    PublishedUrlsRepository,
    KeywordsRepository,
    ScoringConfigRepository,
    ContentExtractor,
    FakeNewsModel,
)
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
    DATA_DIR,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"


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
        content_extractor: ContentExtractor = None,
    ):
        self._verified_repo = verified_repo
        self._content_extractor = content_extractor

    def execute(self) -> dict:
        source = DATA_DIR / "generated_news_articles.json"
        if not source.exists():
            return {"status": "error", "message": f"No existe {source}"}

        with open(source, "r", encoding="utf-8") as f:
            new_articles = json.load(f)

        verified_articles = []
        for art in new_articles:
            title = art.get("title", "")
            content = art.get("content", "")
            slug = art.get("slug", "")

            # Translate title to Spanish
            from src.shared.adapters.translator import translate_text

            title_es = title
            try:
                title_es = translate_text(title[:200], target_lang="es")
            except Exception:
                pass

            verified_article = VerifiedArticle(
                title=title,
                desc=content,
                source=art.get("source", "NBES"),
                origin="Noticias Web",
                url=f"https://nbes.blog/{slug}",
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
                source_url=art.get("source_url", f"https://nbes.blog/{slug}"),
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


class FullVerifyNewsUseCase:
    def __init__(
        self,
        article_repo: ArticleRepository,
        verified_repo: VerifiedNewsRepository,
        published_urls_repo: PublishedUrlsRepository,
        keywords_repo: KeywordsRepository,
        scoring_config_repo: ScoringConfigRepository,
        content_extractor: ContentExtractor = None,
        fake_news_model: FakeNewsModel = None,
        config: dict = None,
    ):
        self._article_repo = article_repo
        self._verified_repo = verified_repo
        self._published_urls_repo = published_urls_repo
        self._keywords_repo = keywords_repo
        self._scoring_config_repo = scoring_config_repo
        self._content_extractor = content_extractor
        self._fake_news_model = fake_news_model
        self._config = config or {}
        self._weights = self._config.get(
            "weights", {"min_score_threshold": 5, "min_chars": 1000}
        )
        self._limits = self._config.get("limits", {"ttl_days": 30, "max_urls": 1000})

    def execute(self) -> dict:
        from src.news.infrastructure.adapters import compute_score, categorizar_noticia
        from src.shared.adapters.mongo_db import get_database

        config = self._scoring_config_repo.get_scoring_config()
        scoring_rules = config.get("scoring_rules", {})
        source_prioritarias = set(config.get("source_prioritarias", set()))
        weights = config.get("weights", {})
        limits = config.get("limits", {})

        trending_keywords = self._keywords_repo.get_trending_keywords()
        breaking_keywords = self._keywords_repo.get_breaking_keywords()

        published_urls = self._published_urls_repo.get_urls(
            limits.get("ttl_days", 30), limits.get("max_urls", 1000)
        )

        raw_articles = self._article_repo.get_all_articles()
        articles_to_process = []
        for article in raw_articles:
            url = article.url
            if url and url not in published_urls:
                articles_to_process.append(article)

        if not articles_to_process:
            return {
                "status": "error",
                "message": "No hay artículos nuevos para procesar.",
            }

        verified = []
        for article in articles_to_process:
            title = article.title
            desc = article.desc

            if self._fake_news_model:
                is_real, confidence = self._fake_news_model.predict(title, desc)
            else:
                is_real, confidence = True, 1.0

            tema = categorizar_noticia(title, desc)
            score = compute_score(
                {
                    "title": title,
                    "desc": desc,
                    "url": article.url,
                    "publishedAt": article.published_at,
                },
                tema,
                confidence,
                scoring_rules,
                source_prioritarias,
                trending_keywords,
                breaking_keywords,
                weights,
            )

            breaking_hits = check_breaking_keywords(title, desc, breaking_keywords)

            if not is_valid_score(
                score, breaking_hits, weights.get("min_score_threshold", 5)
            ):
                continue

            verified_article = VerifiedArticle(
                title=title,
                desc=desc,
                source=article.source,
                origin=article.origin,
                url=article.url,
                publishedAt=datetime.now()
                if not article.published_at
                else article.published_at,
                tema=tema,
                resumen=resumir_noticia(title, desc),
                score=int(score),
                model_prediction="real" if is_real else "fake",
                confidence=confidence,
                verification={"verified": bool(is_real)},
            )
            verified.append(verified_article)

        verificadas_sorted = sort_verified_news([v.to_dict() for v in verified])
        self._verified_repo.save_verified_all(
            [VerifiedArticle.from_dict(v) for v in verificadas_sorted]
        )

        top = verificadas_sorted[0] if verificadas_sorted else None
        if not top:
            self._verified_repo.delete_all_news()
            return {"status": "warning", "message": "Ninguna noticia pasó el filtro."}

        try:
            url = top.get("url")
            if url and self._content_extractor:
                contenido, _ = self._content_extractor.extract(url)
                if len(contenido) >= weights.get("min_chars", 1000):
                    published_urls.add(url)
                    self._published_urls_repo.save_urls(
                        published_urls,
                        limits.get("ttl_days", 30),
                        limits.get("max_urls", 1000),
                    )
                    db = get_database()
                    db["raw_news"].update_one(
                        {"url": url}, {"$set": {"published": True}}
                    )
        except Exception:
            pass

        self._verified_repo.delete_all_news()
        self._verified_repo.insert_news([VerifiedArticle.from_dict(top)])

        return {
            "status": "success",
            "processed": len(articles_to_process),
            "verified": len(verified),
            "saved": 1,
        }


def reload_sources() -> List[dict]:
    from src.news.infrastructure.adapters import MongoRSSSourceRepository

    repo = MongoRSSSourceRepository()
    return repo.get_all_sources()
