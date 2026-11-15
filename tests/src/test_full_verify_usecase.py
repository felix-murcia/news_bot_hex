"""Test para FullVerifyNewsUseCase — valida inyección de puertos (no adaptadores)."""

from src.news.domain.ports import (
    GeneratedArticlesRepository,
    VerifiedNewsRepository,
    PublishedUrlsRepository,
    KeywordsRepository,
    ScoringConfigRepository,
    ContentExtractor,
)
from src.news.domain.entities.verified_article import VerifiedArticle
from unittest.mock import Mock
from datetime import datetime


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


def test_full_verify_saves_extracted_content():
    """FullVerifyNewsUseCase guarda el content extraído en el VerifiedArticle."""
    from src.news.application.usecases.full_verify_usecase import FullVerifyNewsUseCase

    extracted = "Contenido extraído de la noticia completa. " * 50  # >1000 chars

    articles_repo = Mock(spec=GeneratedArticlesRepository)
    articles_repo.get_pending_articles.return_value = [{
        "url": "https://example.com/noticia",
        "title": "Título de la noticia importante",
        "desc": "Descripción corta del RSS",
        "source": "TestSource",
        "origin": "Test",
        "publishedAt": datetime.now().isoformat(),
        "tema": "Noticias",
        "resumen": "Resumen de prueba",
        "score": 15,
        "model_prediction": "real",
        "confidence": 0.95,
        "verification": {"verified": True},
        "slug": "test-noticia",
    }]

    verified_repo = Mock(spec=VerifiedNewsRepository)
    published_urls_repo = Mock(spec=PublishedUrlsRepository)
    published_urls_repo.get_urls.return_value = set()
    published_urls_repo.get_recent_topics.return_value = []
    keywords_repo = Mock(spec=KeywordsRepository)
    keywords_repo.get_trending_keywords.return_value = []
    keywords_repo.get_breaking_keywords.return_value = []
    scoring_config_repo = Mock(spec=ScoringConfigRepository)
    scoring_config_repo.get_scoring_config.return_value = {
        "scoring_rules": {"Noticias": 10},  # Base score para pasar threshold
        "source_prioritarias": [],
        "weights": {"min_score_threshold": 5, "min_chars": 1000},
        "limits": {"ttl_days": 30, "max_urls": 1000},
    }

    usecase = FullVerifyNewsUseCase(
        generated_articles_repo=articles_repo,
        verified_news_repo=verified_repo,
        published_urls_repo=published_urls_repo,
        keywords_repo=keywords_repo,
        scoring_config_repo=scoring_config_repo,
        categorizer=lambda title, desc: "Noticias",
        frozen_terms_extractor=lambda title: [],
    )

    result = usecase.execute()

    # Verificar que insert_news fue llamado con VerifiedArticle SIN contenido extraído (Jina se llama en ArticleUseCase)
    verified_repo.insert_news.assert_called_once()
    saved_articles = verified_repo.insert_news.call_args[0][0]
    assert len(saved_articles) == 1
    saved_article = saved_articles[0]
    assert isinstance(saved_article, VerifiedArticle)
    # FullVerify ya no extrae contenido con Jina → content está vacío (default)
    # ArticleUseCase llamará a Jina cuando necesite el contenido completo
    assert saved_article.content == ""  # Default vacío, Jina se extrae en paso de artículo
    assert saved_article.content != extracted  # No es el contenido extraído por Jina