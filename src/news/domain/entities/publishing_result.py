"""Publishing result value object for tracking publication outcomes."""

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class PublishingResult:
    """Value object for publication result on a single platform."""

    platform: str
    status: str  # "ok", "error", "skipped"
    url: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "platform": self.platform,
            "status": self.status,
            "url": self.url,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PublishingResult":
        """Create from dictionary."""
        return cls(
            platform=data.get("platform", ""),
            status=data.get("status", "error"),
            url=data.get("url"),
            error=data.get("error"),
            duration_ms=data.get("duration_ms"),
        )
