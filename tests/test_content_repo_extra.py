from __future__ import annotations

from pathlib import Path

from backend.infra.content_repo import JSONContentRepository


def test_json_content_repo_reads_and_defaults(tmp_path: Path) -> None:
    path = tmp_path / "content.json"
    repo = JSONContentRepository(str(path))
    # default when missing key
    missing = repo.get_snippet("does-not-exist")
    assert missing["id"] == "does-not-exist"
    assert "text" in missing
    # write a snippet and read it back
    path.write_text('{"hello": {"id": "hello", "text": "world"}}', encoding="utf-8")
    s = repo.get_snippet("hello")
    assert s["text"] == "world"

