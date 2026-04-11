from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class VerifiedArticle:
    title: str
    desc: str
    source: str
    origin: str
    url: str
    publishedAt: datetime
    tema: str
    resumen: str
    score: int
    model_prediction: str
    confidence: float
    verification: dict
    slug: str = ""
    content: str = ""
    labels: Optional[list] = None
    image_url: str = ""
    excerpt: str = ""
    seo_title: str = ""
    focus_keyword: str = ""
    image_credit: str = ""
    is_draft: bool = False
    source_url: str = ""
    alt_text: str = ""
    source_type: str = "news_man"
    original_url: str = ""
    title_es: str = ""

    def __post_init__(self):
        if self.labels is None:
            self.labels = ["Noticias"]

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "desc": self.desc,
            "source": self.source,
            "origin": self.origin,
            "url": self.url,
            "publishedAt": self.publishedAt.isoformat()
            if isinstance(self.publishedAt, datetime)
            else self.publishedAt,
            "tema": self.tema,
            "resumen": self.resumen,
            "score": self.score,
            "model_prediction": self.model_prediction,
            "confidence": self.confidence,
            "verification": self.verification,
            "slug": self.slug,
            "content": self.content,
            "labels": self.labels,
            "image_url": self.image_url,
            "excerpt": self.excerpt,
            "seo_title": self.seo_title,
            "focus_keyword": self.focus_keyword,
            "image_credit": self.image_credit,
            "is_draft": self.is_draft,
            "source_url": self.source_url,
            "alt_text": self.alt_text,
            "source_type": self.source_type,
            "original_url": self.original_url,
            "title_es": self.title_es,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VerifiedArticle":
        published = data.get("publishedAt")
        if isinstance(published, str):
            try:
                published = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except Exception:
                published = datetime.now()
        elif published is None:
            published = datetime.now()

        return cls(
            title=data.get("title", ""),
            desc=data.get("desc", ""),
            source=data.get("source", "NBES"),
            origin=data.get("origin", "Noticias Web"),
            url=data.get("url", ""),
            publishedAt=published,
            tema=data.get("tema", "Noticias"),
            resumen=data.get("resumen", ""),
            score=data.get("score", 10),
            model_prediction=data.get("model_prediction", "real"),
            confidence=data.get("confidence", 0.95),
            verification=data.get("verification", {"verified": True}),
            slug=data.get("slug", ""),
            content=data.get("content", ""),
            labels=data.get("labels", ["Noticias"]),
            image_url=data.get("image_url", ""),
            excerpt=data.get("excerpt", ""),
            seo_title=data.get("seo_title", ""),
            focus_keyword=data.get("focus_keyword", ""),
            image_credit=data.get("image_credit", ""),
            is_draft=data.get("is_draft", False),
            source_url=data.get("source_url", ""),
            alt_text=data.get("alt_text", ""),
            source_type=data.get("source_type", "news_man"),
            original_url=data.get("original_url", ""),
            title_es=data.get("title_es", ""),
        )
