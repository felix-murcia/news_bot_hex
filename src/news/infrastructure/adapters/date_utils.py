import logging
import email.utils
import dateutil.parser
from datetime import datetime, timedelta, timezone

from config.logging_config import get_logger

logger = get_logger("news_bot.infra.news_adapters")


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
