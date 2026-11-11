import json
from pathlib import Path

from src.shared.adapters.json_debug_output_repository import JsonDebugOutputRepository


def test_save_outputs_writes_articles_and_posts(tmp_path: Path):
    repo = JsonDebugOutputRepository(tmp_path)
    article_path = repo.save_outputs(
        "audio",
        {"article": {"title": "T", "content": "C"}},
        {"tweet": "Hola"},
    )
    assert article_path == tmp_path / "generated_audio_articles.json"
    assert article_path.exists()
    assert json.loads(article_path.read_text()) == [{"title": "T", "content": "C"}]
    posts = tmp_path / "generated_audio_posts.json"
    assert json.loads(posts.read_text()) == [{"tweet": "Hola"}]
