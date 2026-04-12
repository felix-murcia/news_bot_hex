import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Set

from src.news.domain.entities.article import Article
from src.news.domain.entities.verified_article import VerifiedArticle
from src.news.domain.ports import (
    RSSSourceRepository,
    ArticleRepository,
    VerifiedNewsRepository,
    PublishedUrlsRepository,
    KeywordsRepository,
    ScoringConfigRepository,
)

from config.logging_config import get_logger

logger = get_logger("news_bot.infra.news_adapters")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"


class MongoRSSSourceRepository(RSSSourceRepository):
    COLLECTION_NAME = "sources_rss"

    def __init__(self):
        from src.shared.adapters.mongo_db import get_database

        self._db = get_database()
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

    def __init__(self):
        from src.shared.adapters.mongo_db import get_database

        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    def get_all_articles(self) -> List[Article]:
        try:
            raw = list(self._collection.find({}))
            return [Article.from_dict(item) for item in raw]
        except Exception as e:
            logger.error(f"Error retrieving raw news: {e}")
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
            return 0


class MongoVerifiedNewsRepository(VerifiedNewsRepository):
    COLLECTION_NAME = "verified_news"

    def __init__(self):
        from src.shared.adapters.mongo_db import get_database

        self._db = get_database()
        self._collection = self._db[self.COLLECTION_NAME]

    def get_all_news(self) -> List[VerifiedArticle]:
        try:
            raw = list(self._collection.find({}, {"_id": 0}))
            return [VerifiedArticle.from_dict(item) for item in raw]
        except Exception as e:
            logger.error(f"Error retrieving verified news: {e}")
            return []

    def get_news_by_url(self, url: str) -> VerifiedArticle | None:
        try:
            raw = self._collection.find_one({"url": url}, {"_id": 0})
            if raw:
                return VerifiedArticle.from_dict(raw)
            return None
        except Exception as e:
            logger.error(f"Error retrieving news by URL: {e}")
            return None

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
        """Returns raw dicts for soft verify (avoids entity conversion overhead)."""
        try:
            raw = list(self._collection.find({}, {"_id": 0}))
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
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["verified_all"]
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

    def __init__(self):
        from src.shared.adapters.mongo_db import get_database

        self._db = get_database()
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
            if existing and "urls" in existing:
                for item in existing["urls"]:
                    if isinstance(item, dict):
                        url_map[item["url"]] = item.get(
                            "published_at", datetime.utcnow().isoformat()
                        )
            now = datetime.utcnow().isoformat()
            for u in urls:
                if u not in url_map:
                    url_map[u] = now
            cutoff = datetime.utcnow() - timedelta(days=ttl_days)
            filtered = [
                {"url": u, "published_at": ts}
                for u, ts in url_map.items()
                if datetime.fromisoformat(ts) > cutoff
            ]
            filtered = sorted(filtered, key=lambda x: x["published_at"])[-max_urls:]
            self._collection.delete_many({})
            self._collection.insert_one({"_id": "urls", "urls": filtered})
            return True
        except Exception as e:
            logger.error(f"Error saving URLs: {e}")
            return False


class MongoKeywordsRepository(KeywordsRepository):
    def __init__(self):
        from src.shared.adapters.mongo_db import get_database

        self._db = get_database()

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


class MongoScoringConfigRepository(ScoringConfigRepository):
    def __init__(self):
        from src.shared.adapters.mongo_db import get_database

        self._db = get_database()

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
            return self._default_config()

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
