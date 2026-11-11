from datetime import datetime
from typing import Optional, Dict

from src.news.domain.entities.verified_article import VerifiedArticle
from src.news.domain.ports import (
    ArticleRepository,
    VerifiedNewsRepository,
    PublishedUrlsRepository,
    KeywordsRepository,
    ScoringConfigRepository,
    ContentExtractor,
    FakeNewsModel,
    FrozenTermsRepository,
    GeneratedArticlesRepository,
)

from config.logging_config import get_logger
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

logger = get_logger("news_bot.usecase.full_verify")


class FullVerifyNewsUseCase:
    """Caso de uso para verificación completa de noticias (DIP: inyección de repositorios)."""

    def __init__(
        self,
        generated_articles_repo: GeneratedArticlesRepository,
        verified_news_repo: VerifiedNewsRepository,
        published_urls_repo: PublishedUrlsRepository,
        keywords_repo: KeywordsRepository,
        scoring_config_repo: ScoringConfigRepository,
        content_extractor: Optional[ContentExtractor] = None,
        fake_news_model: Optional[FakeNewsModel] = None,
        frozen_terms_repo: Optional[FrozenTermsRepository] = None,
        config: Optional[Dict] = None,
    ):
        self.generated_articles_repo = generated_articles_repo
        self._verified_repo = verified_news_repo
        self._published_urls_repo = published_urls_repo
        self._keywords_repo = keywords_repo
        self._scoring_config_repo = scoring_config_repo
        self._content_extractor = content_extractor
        self._fake_news_model = fake_news_model
        self._frozen_terms_repo = frozen_terms_repo
        self._config = config or {}
        self._weights = self._config.get(
            "weights", {"min_score_threshold": 5, "min_chars": 1000}
        )
        self._limits = self._config.get("limits", {"ttl_days": 30, "max_urls": 1000})

    def execute(self) -> dict:
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

        raw_articles = self.generated_articles_repo.load_all()
        articles_to_process = []
        for article in raw_articles:
            url = article.get("original_url") or article.get("url")
            if url and url not in published_urls:
                articles_to_process.append(article)

        if not articles_to_process:
            return {
                "status": "error",
                "message": "No hay artículos nuevos para procesar.",
            }

        verified = []
        for article in articles_to_process:
            title = article.get("title", "")
            desc = article.get("desc", "")

            if self._fake_news_model:
                is_real, confidence = self._fake_news_model.predict(title, desc)
            else:
                is_real, confidence = True, 1.0

            tema = categorizar_noticia(title, desc)
            score = compute_score(
                {
                    "title": title,
                    "desc": desc,
                    "url": article.get("url", ""),
                    "publishedAt": article.get("publishedAt", ""),
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
                source=article.get("source", "NBES"),
                origin=article.get("origin", "Noticias Web"),
                url=article.get("url", ""),
                publishedAt=datetime.now()
                if not article.get("publishedAt")
                else article.get("publishedAt"),
                tema=tema,
                resumen=resumir_noticia(title, desc),
                score=int(score),
                model_prediction="real" if is_real else "fake",
                confidence=confidence,
                verification={"verified": bool(is_real)},
            )
            verified.append(verified_article)

        verificadas_sorted = sort_verified_news([v.to_dict() for v in verified])

        deduplicated = deduplicate_by_similarity(verificadas_sorted)

        recent_topics = self._published_urls_repo.get_recent_topics(hours=24)
        diversified = apply_diversity_penalty(deduplicated, recent_topics)

        if self._frozen_terms_repo:
            frozen_terms = self._frozen_terms_repo.get_active_terms(ttl_hours=5)
            diversified = apply_frozen_terms_penalty(diversified, frozen_terms)

        diversified_sorted = sort_verified_news(diversified)

        self._verified_repo.save_verified_all(
            [VerifiedArticle.from_dict(v) for v in diversified_sorted]
        )

        top = diversified_sorted[0] if diversified_sorted else None
        if not top:
            self._verified_repo.delete_all_news()
            return {"status": "warning", "message": "Ninguna noticia pasó el filtro."}

        url = top.get("url")
        if url and self._content_extractor:
            contenido, _, _titulo = self._content_extractor.extract(url)
            if len(contenido) >= weights.get("min_chars", 1000):
                published_urls.add(url)
                self._published_urls_repo.save_urls(
                    published_urls,
                    limits.get("ttl_days", 30),
                    limits.get("max_urls", 1000),
                )

        url = top.get("url")
        if url and url not in published_urls:
            published_urls.add(url)
            self._published_urls_repo.save_urls(
                published_urls,
                limits.get("ttl_days", 30),
                limits.get("max_urls", 1000),
            )

        tema = top.get("tema", "")
        if url and tema:
            self._published_urls_repo.save_url_with_topic(url, tema)

        title = top.get("title", "")
        if self._frozen_terms_repo and title:
            terms = extract_frozen_terms(title)
            if terms:
                self._frozen_terms_repo.freeze_terms(terms, title)

        self._verified_repo.delete_all_news()
        self._verified_repo.insert_news([VerifiedArticle.from_dict(top)])

        return {
            "status": "success",
            "processed": len(articles_to_process),
            "verified": len(verified),
            "deduplicated": len(deduplicated),
            "saved": 1,
        }