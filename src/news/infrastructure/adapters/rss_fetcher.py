import logging
from datetime import datetime
from typing import List

import requests
import feedparser

from src.news.domain.entities.article import Article
from src.news.domain.ports import RSSFetcher

from src.logging_config import get_logger

logger = get_logger("news_bot.infra.news_adapters")


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
