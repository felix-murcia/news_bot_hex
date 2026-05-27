"""Generated post value object for social media."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class GeneratedPost:
    """Value object for generated social media post."""

    content: str
    image_url: Optional[str] = None
    social_urls: Dict[str, str] = field(default_factory=dict)  # {platform: url}
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "content": self.content,
            "image_url": self.image_url,
            "social_urls": self.social_urls,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeneratedPost":
        """Create from dictionary."""
        return cls(
            content=data.get("content", ""),
            image_url=data.get("image_url"),
            social_urls=data.get("social_urls", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
        )
