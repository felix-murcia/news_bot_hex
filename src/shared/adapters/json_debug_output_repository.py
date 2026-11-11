import json
from pathlib import Path
from typing import Any, Dict

from src.shared.domain.ports.debug_output_repository import DebugOutputRepository


class JsonDebugOutputRepository(DebugOutputRepository):
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir

    def save_outputs(self, kind: str, article_data: Dict[str, Any], post: Dict[str, Any]) -> Path:
        article = article_data.get("article", {})
        articles_path = self._data_dir / f"generated_{kind}_articles.json"
        posts_path = self._data_dir / f"generated_{kind}_posts.json"
        with open(articles_path, "w", encoding="utf-8") as f:
            json.dump([article], f, indent=2, ensure_ascii=False)
        with open(posts_path, "w", encoding="utf-8") as f:
            json.dump([post], f, indent=2, ensure_ascii=False)
        return articles_path
