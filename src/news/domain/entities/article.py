from datetime import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class Article:
    title: str
    url: str
    source: str
    desc: str = ""
    published_at: Optional[datetime] = None
    origin: str = "RSS"
    published: bool = False
    filtered: bool = True

    def to_dict(self) -> dict:
        published_at_value = None
        if self.published_at:
            if isinstance(self.published_at, str):
                published_at_value = self.published_at
            elif hasattr(self.published_at, "isoformat"):
                published_at_value = self.published_at.isoformat() + "Z"

        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "desc": self.desc,
            "publishedAt": published_at_value,
            "origin": self.origin,
            "published": self.published,
            "filtered": self.filtered,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            source=data.get("source", ""),
            desc=data.get("desc", ""),
            published_at=data.get("publishedAt"),
            origin=data.get("origin", "RSS"),
            published=data.get("published", False),
            filtered=data.get("filtered", True),
        )
