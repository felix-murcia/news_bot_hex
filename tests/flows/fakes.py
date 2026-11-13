"""Fakes en memoria para test de flujo completo del pipeline (B27).

Cada fake implementa SOLO los métodos que el pipeline real llama.
Registran las llamadas para que los tests puedan verificar la invocación.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum


# ============================================================================
# Fakes de Repositorios
# ============================================================================

@dataclass
class FakeGeneratedArticlesRepository:
    """Fake para GeneratedArticlesRepository (puerto)."""
    _articles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    calls: List[str] = field(default_factory=list)

    def load_all(self) -> List[Dict[str, Any]]:
        self.calls.append("load_all")
        return list(self._articles.values())

    def save_all(self, articles: List[Dict[str, Any]]) -> bool:
        self.calls.append("save_all")
        for a in articles:
            aid = a.get("_id") or a.get("id") or a.get("url")
            if aid:
                self._articles[str(aid)] = a
        return True

    def delete_all(self) -> bool:
        self.calls.append("delete_all")
        self._articles.clear()
        return True

    def update_tts_audio_path(self, article_id: str, path: str) -> bool:
        self.calls.append(f"update_tts_audio_path:{article_id}")
        if article_id in self._articles:
            self._articles[article_id]["tts_audio_path"] = path
            return True
        return False

    def update_generated_video_path(self, article_id: str, path: str) -> bool:
        self.calls.append(f"update_generated_video_path:{article_id}")
        if article_id in self._articles:
            self._articles[article_id]["video_path"] = path
            return True
        return False

    # Helper para tests
    def add_article(self, article: Dict[str, Any]) -> None:
        aid = article.get("_id") or article.get("id") or article.get("url")
        if aid:
            self._articles[str(aid)] = article


@dataclass
class FakeGeneratedPostsRepository:
    """Fake para GeneratedPostsRepository (puerto)."""
    _posts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    calls: List[str] = field(default_factory=list)

    def load_all(self) -> List[Dict[str, Any]]:
        self.calls.append("load_all")
        return list(self._posts.values())

    def save_all(self, posts: List[Dict[str, Any]]) -> bool:
        self.calls.append("save_all")
        for p in posts:
            pid = p.get("url") or p.get("_id") or str(len(self._posts))
            self._posts[str(pid)] = p
        return True

    def delete_all(self) -> bool:
        self.calls.append("delete_all")
        self._posts.clear()
        return True

    def update_post(self, url: str, updates: Dict[str, Any]) -> bool:
        self.calls.append(f"update_post:{url}")
        if url in self._posts:
            self._posts[url].update(updates)
            return True
        return False


@dataclass
class FakeVerifiedNewsRepository:
    """Fake para VerifiedNewsRepository (puerto)."""
    _news: Dict[str, Any] = field(default_factory=dict)
    calls: List[str] = field(default_factory=list)

    def get_all_news(self) -> List[Any]:
        self.calls.append("get_all_news")
        return list(self._news.values())

    def get_news_by_url(self, url: str) -> Optional[Any]:
        self.calls.append(f"get_news_by_url:{url}")
        return self._news.get(url)

    def insert_news(self, articles: List[Any]) -> bool:
        self.calls.append("insert_news")
        for a in articles:
            url = a.get("url") if isinstance(a, dict) else getattr(a, "url", None)
            if url:
                self._news[url] = a
        return True

    def save_verified_all(self, articles: List[Any]) -> bool:
        self.calls.append("save_verified_all")
        for a in articles:
            url = a.get("url") if isinstance(a, dict) else getattr(a, "url", None)
            if url:
                self._news[url] = a
        return True

    def delete_all_news(self) -> bool:
        self.calls.append("delete_all_news")
        self._news.clear()
        return True

    # Métodos adicionales que usa FullVerifyNewsUseCase
    def get_all_for_soft_verify(self) -> List[Any]:
        self.calls.append("get_all_for_soft_verify")
        return list(self._news.values())


@dataclass
class FakeMongoArticleRepository:
    """Fake para ArticleRepository (RSS) - raw_news."""
    _articles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    calls: List[str] = field(default_factory=list)

    def get_all_articles(self) -> List[Dict[str, Any]]:
        self.calls.append("get_all_articles")
        return list(self._articles.values())

    def get_recent_articles(self, days: int = 2) -> List[Dict[str, Any]]:
        self.calls.append(f"get_recent_articles:{days}")
        return list(self._articles.values())

    def insert_articles(self, articles: List[Dict[str, Any]]) -> bool:
        self.calls.append("insert_articles")
        for a in articles:
            aid = a.get("_id") or a.get("id") or a.get("url")
            if aid:
                self._articles[str(aid)] = a
        return True

    def count_articles(self) -> int:
        self.calls.append("count_articles")
        return len(self._articles)


@dataclass
class FakePublishedUrlsRepository:
    """Fake para PublishedUrlsRepository."""
    _urls: Set[str] = field(default_factory=set)
    calls: List[str] = field(default_factory=list)

    def get_urls(self, ttl_days: int, max_urls: int) -> Set[str]:
        self.calls.append(f"get_urls:ttl={ttl_days},max={max_urls}")
        return self._urls.copy()

    def save_urls(self, urls: Set[str], ttl_days: int, max_urls: int) -> bool:
        self.calls.append(f"save_urls:count={len(urls)}")
        self._urls = urls
        return True

    def save_url_with_topic(self, url: str, tema: str) -> bool:
        self.calls.append(f"save_url_with_topic:{url}")
        self._urls.add(url)
        return True


@dataclass
class FakeMetricsRepository:
    """Fake para MetricsRepositoryPort."""
    saved: List[Any] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)

    def save(self, metric: Any) -> bool:
        self.calls.append("save")
        self.saved.append(metric)
        return True


@dataclass
class FakeKeywordsRepository:
    """Fake para KeywordsRepository."""
    _trending: List[str] = field(default_factory=lambda: ["trending1", "trending2"])
    _breaking: List[str] = field(default_factory=lambda: ["breaking1", "breaking2"])
    calls: List[str] = field(default_factory=list)

    def get_trending_keywords(self) -> List[str]:
        self.calls.append("get_trending_keywords")
        return self._trending

    def get_breaking_keywords(self) -> List[str]:
        self.calls.append("get_breaking_keywords")
        return self._breaking


@dataclass
class FakeScoringConfigRepository:
    """Fake para ScoringConfigRepository."""
    _config: Dict[str, Any] = field(default_factory=lambda: {
        "scoring_rules": {},
        "source_prioritarias": [],
        "weights": {},
        "limits": {"ttl_days": 30, "max_urls": 1000},
    })
    calls: List[str] = field(default_factory=list)

    def get_scoring_config(self) -> Dict[str, Any]:
        self.calls.append("get_scoring_config")
        return self._config


@dataclass
class FakeRSSSourceRepository:
    """Fake para RSSSourceRepository."""
    _sources: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"url": "https://example.com/rss", "name": "Test Source", "enabled": True}
    ])
    calls: List[str] = field(default_factory=list)

    def get_all_sources(self) -> List[Dict[str, Any]]:
        self.calls.append("get_all_sources")
        return self._sources


# ============================================================================
# Fakes de VOs (Value Objects)
# ============================================================================

class FakeAIModel:
    """Fake AI model que devuelve respuestas fijas."""
    def __init__(self, provider: str = "local"):
        self.provider = provider
        self.calls: List[Dict[str, Any]] = []

    def generate(self, prompt: str, **kwargs) -> str:
        self.calls.append({"prompt": prompt, "kwargs": kwargs})
        if "article" in prompt.lower() or "artículo" in prompt.lower():
            # Devolver HTML con <h1> y suficiente contenido
            return (
                "<h1>Título de prueba</h1>"
                "<p>Este es un artículo de prueba con suficiente contenido para pasar "
                "la validación de longitud mínima. " * 50
            )
        elif "tweet" in prompt.lower() or "geopolítica" in prompt.lower():
            return "Tweet de prueba sobre geopolítica #test #geopolitica"
        return "Respuesta genérica"


class FakeAgent:
    """Fake agent con método generate()."""
    def __init__(self, ai_client: FakeAIModel, prefix: str):
        self.ai_client = ai_client
        self.prefix = prefix
        self.calls: List[Dict[str, Any]] = []

    def generate(self, **kwargs) -> str:
        self.calls.append({"kwargs": kwargs})
        # Manejar tanto 'title' como 'topic_or_news' (usado por article agent)
        title = kwargs.get("title") or kwargs.get("topic_or_news", "")
        if "geopolitics" in self.prefix:
            # Para tweet_geopolitics, devolver objeto con publishable/text
            class FakeTweetResponse:
                def __init__(self):
                    self.publishable = True
                    self.text = "Tweet de prueba geopolítica #test #geopolitica"
                    self.reason = ""
            return FakeTweetResponse()
        elif "article_from" in self.prefix or "article" in self.prefix:
            # Para article agents, devolver HTML largo
            if isinstance(title, str) and "Título original" in title:
                # Extraer el título real del prompt
                lines = title.split("\n")
                real_title = lines[0].replace("Título original de la noticia: ", "")
            else:
                real_title = title or "Test Article"
            return (
                f"<h1>{real_title}</h1>"
                "<p>Este es un artículo de prueba con suficiente contenido para pasar "
                "la validación de longitud mínima. " * 100
            )
        return "Respuesta genérica"


@dataclass
class FakeAiProviders:
    """Fake para AiProviders VO."""
    calls: List[str] = field(default_factory=list)

    def adapter_factory(self, provider: str) -> FakeAIModel:
        self.calls.append(f"adapter_factory:{provider}")
        return FakeAIModel(provider)

    def article_agent_factory(self, ai_client: Any) -> FakeAgent:
        self.calls.append("article_agent_factory")
        return FakeAgent(ai_client, "article")

    def article_from_content_agent_factory(self, ai_client: Any, source_type: str) -> FakeAgent:
        self.calls.append(f"article_from_content_agent_factory:{source_type}")
        return FakeAgent(ai_client, f"article_from_{source_type}")

    def tweet_agent_factory(self, ai_client: Any) -> FakeAgent:
        self.calls.append("tweet_agent_factory")
        return FakeAgent(ai_client, "tweet")

    def tweet_geopolitics_agent_factory(self, ai_client: Any) -> FakeAgent:
        self.calls.append("tweet_geopolitics_agent_factory")
        return FakeAgent(ai_client, "tweet_geopolitics")


@dataclass
class FakeWpHelpers:
    """Fake para WpHelpers VO."""
    calls: List[str] = field(default_factory=list)
    token: str = "fake-wp-token"
    post_id_counter: int = 1

    def get_valid_wp_token(self) -> str:
        self.calls.append("get_valid_wp_token")
        return self.token

    def publish_post(self, **kwargs) -> Optional[str]:
        self.calls.append(f"publish_post:{kwargs.get('title', 'no-title')}")
        pid = self.post_id_counter
        self.post_id_counter += 1
        return f"https://wordpress.example.com/?p={pid}"

    def ensure_category(self, name: str, **kwargs) -> Optional[int]:
        self.calls.append(f"ensure_category:{name}")
        return 1

    def ensure_tag(self, name: str, **kwargs) -> Optional[int]:
        self.calls.append(f"ensure_tag:{name}")
        return 1

    def upload_image_from_url(self, url: str, **kwargs) -> Optional[int]:
        self.calls.append(f"upload_image_from_url:{url}")
        return 1

    def upload_audio(self, path: str, **kwargs) -> Optional[int]:
        self.calls.append(f"upload_audio:{path}")
        return 1

    def rest_url(self, endpoint: str) -> str:
        self.calls.append(f"rest_url:{endpoint}")
        return f"https://wordpress.example.com/wp-json/wp/v2/{endpoint}"

    def get_headers(self) -> Dict[str, Any]:
        self.calls.append("get_headers")
        return {"Authorization": f"Bearer {self.token}"}


@dataclass
class FakeImageEnricher:
    """Fake para image enricher."""
    calls: List[str] = field(default_factory=list)

    def enrich(self, posts: List[Dict[str, Any]]) -> None:
        self.calls.append(f"enrich:{len(posts)} posts")
        for p in posts:
            if "image_url" not in p:
                p["image_url"] = "https://fake.image/unsplash.jpg"

    def enrich_from_mongo(self) -> int:
        self.calls.append("enrich_from_mongo")
        return 0

    def enrich_articles_from_mongo(self) -> int:
        self.calls.append("enrich_articles_from_mongo")
        return 0


@dataclass
class FakeImageFetcher:
    """Fake para image fetchers (unsplash, google, wikimedia)."""
    name: str
    calls: List[str] = field(default_factory=list)

    def fetch_for_posts(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.calls.append(f"fetch_for_posts:{len(posts)}")
        return posts


@dataclass
class FakeImageProviders:
    """Fake para ImageProviders VO."""
    calls: List[str] = field(default_factory=list)

    def enricher_factory(self, mode: str) -> FakeImageEnricher:
        self.calls.append(f"enricher_factory:{mode}")
        return FakeImageEnricher()

    def wikimedia_factory(self, mode: str) -> FakeImageFetcher:
        self.calls.append(f"wikimedia_factory:{mode}")
        return FakeImageFetcher(name="wikimedia")

    def google_factory(self, mode: str) -> FakeImageFetcher:
        self.calls.append(f"google_factory:{mode}")
        return FakeImageFetcher(name="google")

    def unsplash_factory(self, mode: str) -> FakeImageFetcher:
        self.calls.append(f"unsplash_factory:{mode}")
        return FakeImageFetcher(name="unsplash")


@dataclass
class FakeSeoHelpers:
    """Fake para SeoHelpers VO."""
    calls: List[str] = field(default_factory=list)

    def slugify(self, text: str, **kwargs) -> str:
        self.calls.append(f"slugify:{text[:30]}")
        return text.lower().replace(" ", "-")[:60]

    def extract_focus_keyphrase(self, text: str, **kwargs) -> str:
        self.calls.append("extract_focus_keyphrase")
        return "test keyphrase"

    def generate_meta_description(self, text: str, *args, **kwargs) -> str:
        self.calls.append("generate_meta_description")
        return "Meta description"

    def truncate_seo_title(self, title: str, **kwargs) -> str:
        self.calls.append("truncate_seo_title")
        return title[:60]

    def clean_title(self, title: str, **kwargs) -> str:
        self.calls.append("clean_title")
        return title

    def generate_excerpt(self, text: str, **kwargs) -> str:
        self.calls.append("generate_excerpt")
        return text[:150]


# ============================================================================
# Fakes de Servicios / Use Cases
# ============================================================================

@dataclass
class FakeTtsUseCase:
    """Fake para TTSFromArticleUseCase."""
    calls: List[str] = field(default_factory=list)

    def execute_batch(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.calls.append(f"execute_batch:{len(articles)} articles")
        updated = []
        for a in articles:
            article_id = a.get("_id") or a.get("id") or a.get("url") or "unknown"
            a_copy = a.copy()
            a_copy["tts_audio_path"] = f"/tmp/audio/{article_id}.mp3"
            updated.append(a_copy)
        return updated


@dataclass
class FakeSocialPublisher:
    """Fake para SocialMediaPublisher facade."""
    calls: List[str] = field(default_factory=list)

    def publish_all(self) -> List[Dict[str, Any]]:
        self.calls.append("publish_all")
        return [
            {"platform": "bluesky", "success": True, "url": "https://bluesky.example.com/post/1"},
            {"platform": "mastodon", "success": True, "url": "https://mastodon.example.com/@user/1"},
            {"platform": "facebook", "success": True, "url": "https://facebook.example.com/post/1"},
        ]


@dataclass
class FakeVideoGenerator:
    """Fake para VideoGeneratorPort."""
    calls: List[str] = field(default_factory=list)
    available: bool = True

    def is_available(self) -> bool:
        self.calls.append("is_available")
        return self.available

    def create_video_from_audio(self, audio_path: str, image: Optional[str] = None) -> Optional[str]:
        self.calls.append(f"create_video_from_audio:{audio_path}")
        return f"/tmp/video/{audio_path.split('/')[-1].replace('.mp3', '.mp4')}"


# ============================================================================
# Callables de pasos del pipeline (runners)
# ============================================================================

def make_rss_fetch_runner(articles_repo: FakeMongoArticleRepository) -> Callable:
    """Runner que simula RSS fetch."""
    def runner() -> Dict[str, Any]:
        # Simula que RSS fetch guarda artículos en raw_news
        test_articles = [
            {
                "title": f"Test Article {i}",
                "url": f"https://example.com/article/{i}",
                "desc": f"Description {i}",
                "publishedAt": "2026-01-01T00:00:00Z",
                "source": "Test Source",
            }
            for i in range(5)
        ]
        articles_repo.insert_articles(test_articles)
        return {"status": "ok", "fetched": 5, "new": 5}
    return runner


def make_full_verify_runner(
    generated_articles_repo: FakeGeneratedArticlesRepository,
    verified_repo: FakeVerifiedNewsRepository,
) -> Callable:
    """Runner que simula Full Verification (pasa artículos a verified_news)."""
    def runner() -> Dict[str, Any]:
        articles = generated_articles_repo.load_all()
        if not articles:
            return {"status": "error", "message": "No hay artículos nuevos para procesar."}

        # Simular verificación: guardar en verified_news
        # Los objetos deben tener to_dict() para el content use case
        for a in articles:
            url = a.get("url")
            if url:
                # VerifiedNewsRepository espera objetos con to_dict()
                class FakeVerifiedArticle:
                    def __init__(self, data):
                        self.__dict__.update(data)
                        # El article use case busca 'content' para obtener el texto completo
                        if "content" not in self.__dict__:
                            self.content = data.get("desc", "")
                    def to_dict(self):
                        return self.__dict__
                
                verified_repo.insert_news([FakeVerifiedArticle(a)])
        
        return {"status": "ok", "verified": len(articles), "saved": len(articles)}
    return runner


def make_image_unsplash_runner() -> Callable:
    """Runner que no hace nada (simula fetch unsplash)."""
    def runner() -> None:
        pass
    return runner


def make_image_google_runner() -> Callable:
    """Runner que no hace nada (simula fetch google)."""
    def runner() -> None:
        pass
    return runner


def make_image_enricher_runner() -> Callable:
    """Runner que no hace nada (simula enrich)."""
    def runner() -> None:
        pass
    return runner


def make_wordpress_runner() -> Callable:
    """Runner que simula publicación WordPress."""
    def runner() -> None:
        pass
    return runner


def make_video_generator_factory() -> Callable[[], FakeVideoGenerator]:
    """Factory que devuelve un FakeVideoGenerator."""
    def factory() -> FakeVideoGenerator:
        return FakeVideoGenerator()
    return factory


def make_cache_loader() -> Callable:
    """Cache loader fake."""
    def loader(url: str) -> tuple:
        return (None, "")  # (content, source)
    return loader


def make_social_truncator() -> Callable:
    """Social truncator fake."""
    def truncate(text: str, limit: int = 280) -> str:
        return text[:limit]
    return truncate


def make_post_editor() -> Callable:
    """Post editor fake."""
    def editor(text: str, **kwargs) -> str:
        return text
    return editor


# ============================================================================
# Helpers para construir el pipeline completo con fakes
# ============================================================================

@dataclass
class PipelineFakes:
    """Contenedor de todos los fakes para fácil acceso en tests."""
    generated_articles_repo: FakeGeneratedArticlesRepository
    generated_posts_repo: FakeGeneratedPostsRepository
    verified_news_repo: FakeVerifiedNewsRepository
    article_repo: FakeMongoArticleRepository
    published_urls_repo: FakePublishedUrlsRepository
    metrics_repo: FakeMetricsRepository
    keywords_repo: FakeKeywordsRepository
    scoring_config_repo: FakeScoringConfigRepository
    rss_source_repo: FakeRSSSourceRepository

    ai_providers: FakeAiProviders
    wp_helpers: FakeWpHelpers
    image_providers: FakeImageProviders
    seo_helpers: FakeSeoHelpers

    tts_usecase: FakeTtsUseCase
    social_publisher: FakeSocialPublisher
    video_generator_factory: Callable[[], FakeVideoGenerator]

    rss_fetch_runner: Callable
    full_verify_runner: Callable
    image_unsplash_runner: Callable
    image_google_runner: Callable
    image_enricher_runner: Callable
    wordpress_runner: Callable

    cache_loader: Callable
    social_truncator: Callable
    post_editor: Callable


def build_pipeline_fakes() -> PipelineFakes:
    """Construye todos los fakes con wiring coherente entre sí."""
    # Repos
    generated_articles_repo = FakeGeneratedArticlesRepository()
    generated_posts_repo = FakeGeneratedPostsRepository()
    verified_news_repo = FakeVerifiedNewsRepository()
    article_repo = FakeMongoArticleRepository()
    published_urls_repo = FakePublishedUrlsRepository()
    metrics_repo = FakeMetricsRepository()
    keywords_repo = FakeKeywordsRepository()
    scoring_config_repo = FakeScoringConfigRepository()
    rss_source_repo = FakeRSSSourceRepository()

    # VOs
    ai_providers = FakeAiProviders()
    wp_helpers = FakeWpHelpers()
    image_providers = FakeImageProviders()
    seo_helpers = FakeSeoHelpers()

    # Servicios
    tts_usecase = FakeTtsUseCase()
    social_publisher = FakeSocialPublisher()
    video_generator_factory = make_video_generator_factory()

    # Runners (callables de pasos)
    rss_fetch_runner = make_rss_fetch_runner(article_repo)
    full_verify_runner = make_full_verify_runner(generated_articles_repo, verified_news_repo)
    image_unsplash_runner = make_image_unsplash_runner()
    image_google_runner = make_image_google_runner()
    image_enricher_runner = make_image_enricher_runner()
    wordpress_runner = make_wordpress_runner()

    # Utils
    cache_loader = make_cache_loader()
    social_truncator = make_social_truncator()
    post_editor = make_post_editor()

    return PipelineFakes(
        generated_articles_repo=generated_articles_repo,
        generated_posts_repo=generated_posts_repo,
        verified_news_repo=verified_news_repo,
        article_repo=article_repo,
        published_urls_repo=published_urls_repo,
        metrics_repo=metrics_repo,
        keywords_repo=keywords_repo,
        scoring_config_repo=scoring_config_repo,
        rss_source_repo=rss_source_repo,
        ai_providers=ai_providers,
        wp_helpers=wp_helpers,
        image_providers=image_providers,
        seo_helpers=seo_helpers,
        tts_usecase=tts_usecase,
        social_publisher=social_publisher,
        video_generator_factory=video_generator_factory,
        rss_fetch_runner=rss_fetch_runner,
        full_verify_runner=full_verify_runner,
        image_unsplash_runner=image_unsplash_runner,
        image_google_runner=image_google_runner,
        image_enricher_runner=image_enricher_runner,
        wordpress_runner=wordpress_runner,
        cache_loader=cache_loader,
        social_truncator=social_truncator,
        post_editor=post_editor,
    )