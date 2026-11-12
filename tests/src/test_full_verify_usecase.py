"""Test para FullVerifyNewsUseCase — valida inyección de puertos (no adaptadores)."""

from src.news.domain.ports import (
    GeneratedArticlesRepository, 
    VerifiedNewsRepository,
    PublishedUrlsRepository,
    KeywordsRepository,
    ScoringConfigRepository,
)
from unittest.mock import Mock


def test_full_verify_usecase_injects_ports():
    """Use-case recibe puertos por constructor, no adaptadores concretos."""
    from src.news.application.usecases.full_verify_usecase import FullVerifyNewsUseCase

    articles_repo = Mock(spec=GeneratedArticlesRepository)
    verified_repo = Mock(spec=VerifiedNewsRepository)
    published_urls_repo = Mock(spec=PublishedUrlsRepository)
    keywords_repo = Mock(spec=KeywordsRepository)
    scoring_config_repo = Mock(spec=ScoringConfigRepository)

    usecase = FullVerifyNewsUseCase(
        generated_articles_repo=articles_repo,
        verified_news_repo=verified_repo,
        published_urls_repo=published_urls_repo,
        keywords_repo=keywords_repo,
        scoring_config_repo=scoring_config_repo,
        categorizer=lambda title, desc: "Noticias",
        frozen_terms_extractor=lambda title: [],
    )

    assert usecase.generated_articles_repo is articles_repo
    assert usecase._verified_repo is verified_repo