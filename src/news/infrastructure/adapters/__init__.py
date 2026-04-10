import logging
import os
import email.utils
import dateutil.parser
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Set, Dict, Tuple
import requests
import feedparser

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")

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


class JinaContentExtractor(ContentExtractor):
    def extract(self, url: str) -> Tuple[str, str]:
        try:
            from src.shared.adapters.jina_extractor import extraer_contenido

            contenido, metodo = extraer_contenido(url)
            return contenido, metodo
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return "", "error"


class DummyFakeNewsModel(FakeNewsModel):
    def predict_batch(self, texts: List[str]) -> Tuple[List[bool], List[float]]:
        return [True] * len(texts), [1.0] * len(texts)

    def predict(self, title: str, desc: str) -> Tuple[bool, float]:
        return True, 1.0


def parse_date_flexible(date_input) -> datetime | None:
    if not date_input:
        return None
    date_str = str(date_input).strip()
    try:
        if "GMT" in date_str.upper() or (
            "," in date_str and len(date_str.split()) >= 5
        ):
            parsed = email.utils.parsedate_tz(date_str)
            if parsed:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
        return dateutil.parser.isoparse(date_str)
    except Exception:
        try:
            return dateutil.parser.parse(date_str, ignoretz=False)
        except Exception:
            return None


def is_today_or_yesterday(dt: datetime) -> bool:
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    today = now.date()
    yesterday = (now - timedelta(days=1)).date()
    return dt.astimezone(timezone.utc).date() in (today, yesterday)


def get_article_date(article) -> str | None:
    keys = [
        "publishedAt",
        "pubDate",
        "published",
        "date",
        "updated",
        "updatedAt",
        "dc:date",
        "dc:created",
        "lastBuildDate",
        "atom:updated",
        "rss:pubDate",
    ]
    for key in keys:
        val = article.get(key)
        if val and isinstance(val, (str, int, float)) and str(val).strip():
            return str(val).strip()
    return None


class FeedparserRSSFetcher(RSSFetcher):
    def fetch(self, url: str, source: str, origin: str = "RSS") -> List[Article]:
        try:
            resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            if "text/html" in resp.headers.get("Content-Type", ""):
                logger.warning(f"[RSS] {source} devolvió HTML en vez de RSS → ignorado")
                return []
            if resp.status_code >= 400:
                logger.warning(f"[RSS] {source} devolvió {resp.status_code} → ignorado")
                return []
            feed = feedparser.parse(resp.content)
            if feed.bozo:
                logger.warning(f"[RSS] {source} feed corrupto → ignorado")
                return []
            articles = []
            for entry in feed.entries:
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                published_iso = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    dt = datetime(*entry.published_parsed[:6])
                    published_iso = dt.isoformat() + "Z"
                articles.append(
                    Article(
                        title=title,
                        url=link,
                        source=source,
                        desc=summary,
                        published_at=published_iso,
                        origin=origin,
                        published=False,
                        filtered=True,
                    )
                )
            return articles
        except Exception as e:
            logger.warning(f"[RSS] Error al obtener {source}: {e}")
            return []


def compute_score(
    article: dict,
    tema: str,
    confidence: float,
    scoring_rules: dict,
    source_prioritarias: set,
    trending_keywords: list,
    breaking_keywords: list,
    weights: dict,
) -> int:
    score = scoring_rules.get(tema, 0)
    pub = article.get("publishedAt")
    if pub:
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if dt > datetime.utcnow() - timedelta(hours=24):
                score += 2
            elif dt > datetime.utcnow() - timedelta(days=3):
                score += 1
        except Exception:
            pass
    source = article.get("source")
    source_name = (
        source.get("name", "") if isinstance(source, dict) else str(source or "")
    )
    if source_name in source_prioritarias:
        score += 2
    if confidence > 0.9:
        score += 1
    text = f"{article.get('title', '')} {article.get('desc', '')}".lower()
    matched_trends = [t for t in trending_keywords if t and t in text]
    if matched_trends:
        score += min(
            weights.get("max_trending_bonus", 3),
            len(matched_trends) * weights.get("trending_weight", 1),
        )
    matched_breaking = [kw for kw in breaking_keywords if kw and kw in text]
    if matched_breaking:
        score += min(
            weights.get("max_breaking_bonus", 4),
            len(matched_breaking) * weights.get("breaking_weight", 2),
        )
    return score


def categorizar_noticia(title: str, desc: str) -> str:
    try:
        from src.shared.adapters.categorizacion import etiquetar_tematica

        return etiquetar_tematica(title, desc)
    except Exception:
        return "Noticias"


def check_breaking_keywords(title: str, desc: str, breaking_keywords: List[str]) -> int:
    text = f"{title} {desc}".lower()
    tokens = set(re.findall(r"\b\w+\b", text))
    return sum(
        1
        for kw in breaking_keywords
        if any(word in tokens for word in kw.lower().split())
    )


def is_valid_score(
    score: float, breaking_hits: int, min_score_threshold: int = 5
) -> bool:
    return score > min_score_threshold or breaking_hits > 2


def sort_verified_news(news_list: List[Dict]) -> List[Dict]:
    def sort_key(item):
        return (
            int(item.get("score", 0)),
            parse_iso_date(item.get("publishedAt") or ""),
        )

    return sorted(news_list, key=sort_key, reverse=True)


def parse_iso_date(date_str: str) -> datetime:
    if not date_str:
        return datetime.min
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.min


def resumir_noticia(title: str, desc: str) -> str:
    resumen = f"{title.strip()}. {desc.strip()}" if desc else title.strip()
    return (resumen[:247] + "...") if len(resumen) > 250 else resumen
