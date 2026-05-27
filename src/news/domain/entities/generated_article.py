"""Generated article value object."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class GeneratedArticle:
    """Value object for generated article with all metadata."""

    title: str
    url: str
    content: str
    image_urls: List[str] = field(default_factory=list)
    tts_audio_path: Optional[str] = None
    video_path: Optional[str] = None
    wp_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "image_urls": self.image_urls,
            "tts_audio_path": self.tts_audio_path,
            "video_path": self.video_path,
            "wp_url": self.wp_url,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeneratedArticle":
        """Create from dictionary."""
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            content=data.get("content", ""),
            image_urls=data.get("image_urls", []),
            tts_audio_path=data.get("tts_audio_path"),
            video_path=data.get("video_path"),
            wp_url=data.get("wp_url"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
        )
