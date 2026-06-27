from abc import ABC, abstractmethod
from typing import List
from src.news.domain.entities.article import Article
from src.news.domain.entities.verified_article import VerifiedArticle
from src.news.domain.ports.metrics_repository_port import MetricsRepositoryPort


class RSSSourceRepository(ABC):
    """Puerto para obtener fuentes RSS."""

    @abstractmethod
    def get_all_sources(self) -> List[dict]:
        pass

    @abstractmethod
    def get_source_by_origin(self, origin: str) -> dict | None:
        pass


class ArticleRepository(ABC):
    """Puerto para gestionar artículos."""

    @abstractmethod
    def get_all_articles(self) -> List[Article]:
        pass

    @abstractmethod
    def get_recent_articles(self, days: int = 2) -> List[Article]:
        pass

    @abstractmethod
    def insert_articles(self, articles: List[Article]) -> bool:
        pass

    @abstractmethod
    def count_articles(self) -> int:
        pass


class RSSFetcher(ABC):
    """Puerto para obtener feeds RSS."""

    @abstractmethod
    def fetch(self, url: str, source: str, origin: str) -> List[Article]:
        pass


class VerifiedNewsRepository(ABC):
    """Puerto para gestionar noticias verificadas."""

    @abstractmethod
    def get_all_news(self) -> List[VerifiedArticle]:
        pass

    @abstractmethod
    def get_news_by_url(self, url: str) -> VerifiedArticle | None:
        pass

    @abstractmethod
    def get_verified_news(self) -> List[VerifiedArticle]:
        pass

    @abstractmethod
    def insert_news(self, articles: List[VerifiedArticle]) -> bool:
        pass

    @abstractmethod
    def delete_all_news(self) -> bool:
        pass

    @abstractmethod
    def save_verified_all(self, articles: List[VerifiedArticle]) -> bool:
        pass


class PublishedUrlsRepository(ABC):
    """Puerto para gestionar URLs publicadas."""

    @abstractmethod
    def get_urls(self, ttl_days: int, max_urls: int) -> set:
        pass

    @abstractmethod
    def save_urls(self, urls: set, ttl_days: int, max_urls: int) -> bool:
        pass

    @abstractmethod
    def get_recent_topics(self, hours: int = 24) -> dict:
        pass

    @abstractmethod
    def save_url_with_topic(self, url: str, tema: str) -> bool:
        pass


class FrozenTermsRepository(ABC):
    """Puerto para gestionar términos congelados tras publicación."""

    @abstractmethod
    def get_active_terms(self, ttl_hours: int = 5) -> list:
        pass

    @abstractmethod
    def freeze_terms(self, terms: list, title: str) -> bool:
        pass


class KeywordsRepository(ABC):
    """Puerto para gestionar keywords."""

    @abstractmethod
    def get_breaking_keywords(self) -> List[str]:
        pass

    @abstractmethod
    def get_trending_keywords(self) -> List[str]:
        pass


class ScoringConfigRepository(ABC):
    """Puerto para obtener configuración de scoring."""

    @abstractmethod
    def get_scoring_config(self) -> dict:
        pass


class ContentExtractor(ABC):
    """Puerto para extraer contenido de URLs."""

    @abstractmethod
    def extract(self, url: str) -> tuple[str, str]:
        pass


class GeneratedPostsRepository(ABC):
    """Puerto para gestionar posts generados (tweets/content)."""

    @abstractmethod
    def load_all(self) -> List[dict]:
        pass

    @abstractmethod
    def save_all(self, posts: List[dict]) -> bool:
        pass

    @abstractmethod
    def delete_all(self) -> bool:
        pass


class GeneratedArticlesRepository(ABC):
    """Puerto para gestionar artículos generados."""

    @abstractmethod
    def load_all(self) -> List[dict]:
        pass

    @abstractmethod
    def save_all(self, articles: List[dict]) -> bool:
        pass

    @abstractmethod
    def delete_all(self) -> bool:
        pass


class FakeNewsModel(ABC):
    """Puerto para el modelo de detección de fake news."""

    @abstractmethod
    def predict_batch(self, texts: List[str]) -> tuple[List[bool], List[float]]:
        pass

    @abstractmethod
    def predict(self, title: str, desc: str) -> tuple[bool, float]:
        pass
