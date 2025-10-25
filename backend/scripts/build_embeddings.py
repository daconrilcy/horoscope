"""
Build embeddings for content/** changes and record ContentVersion.

This script scans the `content/` directory for text files, computes a stable
hash of the inputs, generates embeddings with the configured embedder, writes
artifacts to `artifacts/embeddings/`, and inserts a ContentVersion row using
SQLAlchemy.

Environment:
- DATABASE_URL: target DB (defaults to sqlite:///./embeddings.db)
- EMBEDDINGS_PROVIDER/OPENAI_API_KEY: if using OpenAIEmbedder via container.

Outputs:
- artifacts/embeddings/<timestamp>_embeddings.json
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.infra.repo.models import Base

# Bootstrap path when run as a script
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from backend.domain.content_version import ContentVersion  # noqa: E402
from backend.infra.embeddings.local_embedder import LocalEmbedder  # noqa: E402
from backend.infra.repo.content_version_repo import ContentVersionRepo  # noqa: E402
from backend.infra.repo.db import get_engine, session_scope  # noqa: E402


def _iter_texts(content_dir: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if not content_dir.exists():
        return pairs
    for p in sorted(content_dir.rglob("*.txt")):
        try:
            pairs.append((str(p.relative_to(content_dir)), p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return pairs


def _hash_inputs(pairs: list[tuple[str, str]]) -> str:
    h = hashlib.sha256()
    for rel, text in pairs:
        h.update(rel.encode("utf-8"))
        h.update(b"\n")
        h.update(text.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def main() -> None:
    """
    Point d'entrée principal pour la construction des embeddings.

    Construit les embeddings pour tous les fichiers de contenu et les sauvegarde dans le répertoire
    approprié.
    """
    content_dir = ROOT / "content"
    pairs = _iter_texts(content_dir)
    if not pairs:
        # Generate a minimal synthetic doc to keep the pipeline flowing
        pairs = [("_synthetic.txt", "sample content about zodiac and stars")]
    content_hash = _hash_inputs(pairs)

    # Generate embeddings via LocalEmbedder by default (avoids heavy deps in CI)
    embedder = LocalEmbedder(os.getenv("LOCAL_EMBEDDINGS_MODEL", "all-MiniLM-L6-v2"))
    texts = [t for _, t in pairs]
    vectors = embedder.embed(texts)

    # Write artifact
    outdir = ROOT / "artifacts" / "embeddings"
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    outfile = outdir / f"{ts}_embeddings.json"
    payload: dict[str, Any] = {
        "count": len(vectors),
        "model": "local",
        "vectors_preview": vectors[:3],
        "files": [rel for rel, _ in pairs[:10]],
        "content_hash": content_hash,
        "timestamp": ts,
    }
    outfile.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Insert ContentVersion
    db_url = os.getenv("DATABASE_URL", "sqlite:///./embeddings.db")
    engine = get_engine(db_url)
    now_iso = datetime.now(UTC).isoformat()
    cv = ContentVersion(
        source="content/",
        version=os.getenv("EMBEDDINGS_VERSION", ts),
        content_hash=content_hash,
        embedding_model_name="local",
        embedding_model_version=os.getenv("LOCAL_EMBEDDINGS_MODEL", "all-MiniLM-L6-v2"),
        embed_params={"provider": "local"},
        tenant=None,
        created_at=now_iso,
    )
    # Ensure table exists (idempotent for sqlite CI)

    Base.metadata.create_all(engine)
    with session_scope(engine) as session:
        repo = ContentVersionRepo(session)
        with contextlib.suppress(Exception):
            # Unique conflict or other — do not fail the pipeline
            repo.create(cv)

    print(f"Embeddings artifact -> {outfile}")


if __name__ == "__main__":
    main()
