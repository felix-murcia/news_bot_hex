from datetime import datetime, timedelta
from typing import List, Set
from bson import ObjectId
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from src.news.domain.entities.article import Article
from src.news.domain.entities.verified_article import VerifiedArticle
from src.news.domain.exceptions import RepositoryError
from src.news.domain.ports import (
    RSSSourceRepository,
    ArticleRepository,
    VerifiedNewsRepository,
    PublishedUrlsRepository,
    FrozenTermsRepository,
    KeywordsRepository,
    ScoringConfigRepository,
    GeneratedPostsRepository,
    GeneratedArticlesRepository,
)

from config.logging_config import get_logger


# Tracking query parameters to strip for URL normalization
TRACKING_QUERY_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "traffic_source", "fbclid", "gclid", "msclkid", "ref", "source",
    "share", "cid", "variant", "segment", "mc_cid", "mc_eid",
})

logger = get_logger("news_bot.infra.news_adapters")


class MongoRSSSourceRepository(RSSSourceRepository):
    COLLECTION_NAME = "sources_rss"

    def __init__(self, db=None):
        if db is None:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
        self._db = db
        self._collection = self._db[self.COLLECTION_NAME]

    def get_all_sources(self) -> List[dict]:
        try:
            result = self._collection.find_one({"_id": "sources"})
            if result and "sources" in result:
                return result["sources"]
            return []
        except Exception as e:
            logger.error(f"Error retrieving RSS sources: {e}")
            return []

    def get_source_by_origin(self, origin: str) -> dict | None:
        sources = self.get_all_sources()
        for src in sources:
            if src.get("origin") == origin:
                return src
        return None


class MongoArticleRepository(ArticleRepository):
    COLLECTION_NAME = "raw_news"

    def __init__(self, db=None):
        if db is None:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
        self._db = db
        self._collection = self._db[self.COLLECTION_NAME]

    def get_all_articles(self) -> List[Article]:
        try:
            raw = list(self._collection.find({}))
            return [Article.from_dict(item) for item in raw]
        except Exception as e:
            logger.error(f"Error retrieving raw news: {e}")
            return []

    def get_recent_articles(self, days: int = 2) -> List[Article]:
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
            raw = list(self._collection.find(
                {"publishedAt": {"$gte": cutoff}},
            ))
            if not raw:
                raw = list(self._collection.find({}).sort("_id", -1).limit(500))
            logger.info(f"[RAW] Loaded {len(raw)} recent articles (last {days} days)")
            return [Article.from_dict(item) for item in raw]
        except Exception as e:
            logger.error(f"Error retrieving recent raw news: {e}")
            return []

    def insert_articles(self, articles: List[Article]) -> bool:
        try:
            data = [a.to_dict() for a in articles]
            self._collection.insert_many(data)
            return True
        except Exception as e:
            logger.error(f"Error inserting raw news: {e}")
            return False

    def count_articles(self) -> int:
        try:
            return self._collection.count_documents({})
        except Exception as e:
            logger.error(f"Error counting raw news: {e}")
            raise RepositoryError(f"Error counting articles: {e}") from e


class MongoVerifiedNewsRepository(VerifiedNewsRepository):
    COLLECTION_NAME = "verified_news"

    def __init__(self, db=None):
        if db is None:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
        self._db = db
        self._collection = self._db[self.COLLECTION_NAME]

    def get_all_news(self) -> List[VerifiedArticle]:
        try:
            raw = list(self._collection.find({}, {"_id": 0}))
            return [VerifiedArticle.from_dict(item) for item in raw]
        except Exception as e:
            logger.error(f"Error retrieving verified news: {e}")
            return []

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize URL for comparison: strip tracking params, trailing slash, lowercase scheme/host/path."""
        try:
            parsed = urlparse(url)
            # Lowercase scheme, host, and path
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            path = parsed.path.rstrip("/").lower() or "/"
            # Strip tracking query parameters
            query_params = parse_qsl(parsed.query, keep_blank_values=True)
            filtered_params = [(k, v) for k, v in query_params if k.lower() not in TRACKING_QUERY_PARAMS]
            query = urlencode(filtered_params)
            # Reconstruct normalized URL
            normalized = urlunparse((scheme, netloc, path, parsed.params, query, ""))
            return normalized
        except Exception:
            return url.strip().rstrip("/").lower()

    def _get_url_variants(self, url: str) -> List[str]:
        """Generate URL variants to try for matching."""
        normalized = self._normalize_url(url)
        variants = [url, normalized]
        # Also try with/without trailing slash
        if url.endswith("/"):
            variants.append(url.rstrip("/"))
        else:
            variants.append(url + "/")
        if normalized.endswith("/"):
            variants.append(normalized.rstrip("/"))
        else:
            variants.append(normalized + "/")
        # Deduplicate preserving order
        seen = set()
        unique = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                unique.append(v)
        return unique

    def get_news_by_url(self, url: str) -> VerifiedArticle | None:
        try:
            # Try exact match first (fast path)
            raw = self._collection.find_one({"url": url}, {"_id": 0})
            if raw:
                return VerifiedArticle.from_dict(raw)
            # Try normalized variants
            for variant in self._get_url_variants(url):
                if variant == url:
                    continue
                raw = self._collection.find_one({"url": variant}, {"_id": 0})
                if raw:
                    logger.debug(f"[VERIFIED_REPO] Matched URL via variant: {variant} (original: {url})")
                    return VerifiedArticle.from_dict(raw)
            return None
        except Exception as e:
            logger.error(f"Error retrieving news by URL: {e}")
            raise RepositoryError(f"Error retrieving news by URL: {e}") from e

    def get_verified_news(self) -> List[VerifiedArticle]:
        try:
            raw = list(
                self._collection.find({"verification.verified": True}, {"_id": 0})
            )
            return [VerifiedArticle.from_dict(item) for item in raw]
        except Exception as e:
            logger.error(f"Error retrieving verified news: {e}")
            return []

    def get_all_for_soft_verify(self) -> List[dict]:
        """Returns raw dicts for soft verify from verified_all collection."""
        try:
            coll = self._db["verified_all"]
            raw = list(coll.find({}, {"_id": 0}))
            return raw
        except Exception as e:
            logger.error(f"Error loading all verified news for soft verify: {e}")
            return []

    def insert_news(self, articles: List[VerifiedArticle]) -> bool:
        try:
            data = [a.to_dict() for a in articles]
            self._collection.insert_many(data)
            return True
        except Exception as e:
            logger.error(f"Error inserting verified news: {e}")
            return False

    def delete_all_news(self) -> bool:
        try:
            self._collection.delete_many({})
            return True
        except Exception as e:
            logger.error(f"Error deleting verified news: {e}")
            return False

    def save_verified_all(self, articles: List[VerifiedArticle]) -> bool:
        try:
            coll = self._db["verified_all"]
            coll.delete_many({})
            if articles:
                data = [a.to_dict() for a in articles]
                coll.insert_many(data)
            return True
        except Exception as e:
            logger.error(f"Error saving verified_all: {e}")
            return False


class MongoPublishedUrlsRepository(PublishedUrlsRepository):
    COLLECTION_NAME = "published_urls"

    def __init__(self, db=None):
        if db is None:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
        self._db = db
        self._collection = self._db[self.COLLECTION_NAME]

    def get_urls(self, ttl_days: int, max_urls: int) -> set:
        try:
            data = self._collection.find_one({})
            urls_data = data.get("urls", []) if data else []
            cutoff = datetime.utcnow() - timedelta(days=ttl_days)
            cleaned = []
            for item in urls_data:
                if isinstance(item, dict) and "url" in item:
                    try:
                        ts = datetime.fromisoformat(item.get("published_at"))
                    except Exception:
                        ts = datetime.utcnow()
                    if ts > cutoff:
                        cleaned.append(
                            {"url": item["url"], "published_at": ts.isoformat()}
                        )
            cleaned = sorted(cleaned, key=lambda x: x["published_at"])[-max_urls:]
            return {c["url"] for c in cleaned}
        except Exception as e:
            logger.error(f"Error loading URLs: {e}")
            return set()

    def save_urls(self, urls: Set[str], ttl_days: int, max_urls: int) -> bool:
        try:
            existing = self._collection.find_one({"_id": "urls"})
            url_map = {}
            tema_map = {}
            if existing and "urls" in existing:
                for item in existing["urls"]:
                    if isinstance(item, dict):
                        url_map[item["url"]] = item.get(
                            "published_at", datetime.utcnow().isoformat()
                        )
                        if item.get("tema"):
                            tema_map[item["url"]] = item["tema"]
            now = datetime.utcnow().isoformat()
            for u in urls:
                if u not in url_map:
                    url_map[u] = now
            cutoff = datetime.utcnow() - timedelta(days=ttl_days)
            filtered = []
            for u, ts in url_map.items():
                if datetime.fromisoformat(ts) > cutoff:
                    entry = {"url": u, "published_at": ts}
                    if u in tema_map:
                        entry["tema"] = tema_map[u]
                    filtered.append(entry)
            filtered = sorted(filtered, key=lambda x: x["published_at"])[-max_urls:]
            self._collection.delete_many({})
            self._collection.insert_one({"_id": "urls", "urls": filtered})
            return True
        except Exception as e:
            logger.error(f"Error saving URLs: {e}")
            return False

    def get_recent_topics(self, hours: int = 24) -> dict:
        try:
            data = self._collection.find_one({"_id": "urls"})
            urls_data = data.get("urls", []) if data else []
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            topic_counts = {}
            for item in urls_data:
                if isinstance(item, dict) and item.get("published_at", "") > cutoff:
                    tema = item.get("tema", "")
                    if tema:
                        topic_counts[tema] = topic_counts.get(tema, 0) + 1
            return topic_counts
        except Exception as e:
            logger.error(f"Error getting recent topics: {e}")
            return {}

    def save_url_with_topic(self, url: str, tema: str) -> bool:
        try:
            existing = self._collection.find_one({"_id": "urls"})
            urls = existing.get("urls", []) if existing else []
            for item in urls:
                if isinstance(item, dict) and item.get("url") == url:
                    item["tema"] = tema
                    break
            else:
                urls.append({
                    "url": url,
                    "published_at": datetime.utcnow().isoformat(),
                    "tema": tema,
                })
            self._collection.update_one(
                {"_id": "urls"},
                {"$set": {"urls": urls}},
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"Error saving URL with topic: {e}")
            return False


class MongoKeywordsRepository(KeywordsRepository):
    def __init__(self, db=None):
        if db is None:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
        self._db = db

    def get_breaking_keywords(self) -> List[str]:
        try:
            coll = self._db["breaking_keywords"]
            data = coll.find_one({})
            if data and "breaking_keywords" in data:
                return [w.lower() for w in data["breaking_keywords"]]
            return []
        except Exception as e:
            logger.error(f"Error loading breaking keywords: {e}")
            return []

    def get_trending_keywords(self) -> List[str]:
        try:
            coll = self._db["trending_keywords"]
            data = coll.find_one({})
            if data and "trending_keywords" in data:
                return [w.lower() for w in data["trending_keywords"]]
            return []
        except Exception as e:
            logger.error(f"Error loading trending keywords: {e}")
            return []


class MongoFrozenTermsRepository(FrozenTermsRepository):
    COLLECTION_NAME = "frozen_terms"

    def __init__(self, db=None):
        if db is None:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
        self._db = db
        self._collection = self._db[self.COLLECTION_NAME]

    def get_active_terms(self, ttl_hours: int = 5) -> list:
        try:
            cutoff = (datetime.utcnow() - timedelta(hours=ttl_hours)).isoformat()
            entries = list(self._collection.find(
                {"frozen_at": {"$gte": cutoff}},
                {"_id": 0},
            ))
            terms = set()
            for entry in entries:
                terms.update(entry.get("terms", []))
            return sorted(terms)
        except Exception as e:
            logger.error(f"Error loading frozen terms: {e}")
            return []

    def freeze_terms(self, terms: list, title: str) -> bool:
        try:
            self._collection.insert_one({
                "terms": terms,
                "title": title,
                "frozen_at": datetime.utcnow().isoformat(),
            })
            cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat()
            self._collection.delete_many({"frozen_at": {"$lt": cutoff}})
            return True
        except Exception as e:
            logger.error(f"Error freezing terms: {e}")
            return False


class MongoScoringConfigRepository(ScoringConfigRepository):
    def __init__(self, db=None):
        if db is None:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
        self._db = db

    def get_scoring_config(self) -> dict:
        try:
            coll = self._db["scoring"]
            config = coll.find_one({})
            if config:
                config.pop("_id", None)
                return config
            return self._default_config()
        except Exception as e:
            logger.error(f"Error loading scoring config: {e}")
            raise RepositoryError(f"Error loading scoring config: {e}") from e

    def _default_config(self) -> dict:
        return {
            "scoring_rules": {
                "Politics": 5,
                "Technology": 5,
                "Sports": 5,
                "Entertainment": 4,
                "Business": 5,
                "Science": 4,
                "Health": 4,
                "Noticias": 3,
            },
            "source_prioritarias": set(),
            "weights": {
                "min_score_threshold": 5,
                "min_chars": 1000,
                "trending_weight": 1,
                "max_trending_bonus": 3,
                "breaking_weight": 2,
                "max_breaking_bonus": 4,
            },
            "limits": {"ttl_days": 30, "max_urls": 1000},
        }


class MongoGeneratedPostsRepository(GeneratedPostsRepository):
    """Repositorio de posts generados (tweets/content)."""

    COLLECTION_NAME = "generated_posts"

    def __init__(self, db=None):
        if db is None:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
        self._db = db
        self._collection = self._db[self.COLLECTION_NAME]

    def load_all(self) -> List[dict]:
        try:
            posts = list(self._collection.find({}))
            for p in posts:
                p.pop("_id", None)
            return posts
        except Exception as e:
            logger.error(f"Error loading generated posts: {e}")
            raise RepositoryError(f"Error loading generated posts: {e}") from e

    def save_all(self, posts: List[dict]) -> bool:
        try:
            self._collection.delete_many({})
            if posts:
                self._collection.insert_many(posts)
            logger.info(f"Saved {len(posts)} generated posts")
            return True
        except Exception as e:
            logger.error(f"Error saving generated posts: {e}")
            return False

    def delete_all(self) -> bool:
        try:
            self._collection.delete_many({})
            return True
        except Exception as e:
            logger.error(f"Error deleting generated posts: {e}")
            return False

    def update_post(self, url: str, updates: dict) -> bool:
        try:
            self._collection.update_one({"url": url}, {"$set": updates})
            return True
        except Exception as e:
            logger.error(f"Error updating generated post {url}: {e}")
            return False


class MongoGeneratedArticlesRepository(GeneratedArticlesRepository):
    """Repositorio de artículos generados."""

    COLLECTION_NAME = "generated_articles"

    def __init__(self, db=None):
        if db is None:
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
        self._db = db
        self._collection = self._db[self.COLLECTION_NAME]

    def load_all(self) -> List[dict]:
        try:
            articles = list(self._collection.find({}))
            for a in articles:
                a.pop("_id", None)
            return articles
        except Exception as e:
            logger.error(f"Error loading generated articles: {e}")
            raise RepositoryError(f"Error loading generated articles: {e}") from e

    def save_all(self, articles: List[dict]) -> bool:
        try:
            self._collection.delete_many({})
            if articles:
                for a in articles:
                    a.setdefault("status", "pending")
                self._collection.insert_many(articles)
            logger.info(f"Saved {len(articles)} generated articles")
            return True
        except Exception as e:
            logger.error(f"Error saving generated articles: {e}")
            return False

    def get_pending_articles(self, limit: int = 1000) -> List[dict]:
        """Devuelve solo artículos con status='pending' (query eficiente, sin load_all)."""
        try:
            articles = list(
                self._collection.find({"status": "pending"}).limit(limit)
            )
            for a in articles:
                a.pop("_id", None)
            logger.info(f"Cargados {len(articles)} artículos pending (límite={limit})")
            return articles
        except Exception as e:
            logger.error(f"Error loading pending articles: {e}")
            raise RepositoryError(f"Error loading pending articles: {e}") from e

    def mark_verified(self, urls: List[str]) -> bool:
        """Marca artículos como 'verified' para no reprocesarlos en futuros runs."""
        if not urls:
            return True
        try:
            result = self._collection.update_many(
                {"url": {"$in": urls}},
                {"$set": {"status": "verified"}},
            )
            logger.info(f"Marcados {result.modified_count} artículos como verified")
            return True
        except Exception as e:
            logger.error(f"Error marking articles as verified: {e}")
            return False

    def delete_all(self) -> bool:
        try:
            self._collection.delete_many({})
            return True
        except Exception as e:
            logger.error(f"Error deleting generated articles: {e}")
            return False

    def update_tts_audio_path(self, article_id: str, path: str) -> bool:
        try:
            result = self._collection.update_one(
                {"_id": ObjectId(article_id)},
                {"$set": {"tts_audio_path": path}},
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating tts_audio_path for article {article_id}: {e}")
            return False

    def update_generated_video_path(self, article_id: str, path: str) -> bool:
        try:
            result = self._collection.update_one(
                {"_id": ObjectId(article_id)},
                {"$set": {"generated_video_path": path}},
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating generated_video_path for article {article_id}: {e}")
            return False
