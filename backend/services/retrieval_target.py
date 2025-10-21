"""Target adapter resolution for retrieval migration (dual-write/shadow-read).

Resolves a secondary backend used as migration target. Defaults to "weaviate".
"""

from __future__ import annotations

import os



def get_target_backend_name() -> str:
    """Return the configured migration target backend name."""
    return (os.getenv("RETRIEVAL_TARGET_BACKEND") or os.getenv("RETRIEVAL_MIGRATION_TARGET") or "weaviate").lower()


def get_target_adapter():
    """Construct the adapter for the migration target backend.

    Supports: weaviate | pinecone | elastic (defaults to weaviate).
    """
    name = get_target_backend_name()
    # Import adapters lazily to avoid circular import during module load
    from backend.services.retrieval_proxy import (
        ElasticVectorAdapter,
        PineconeAdapter,
        WeaviateAdapter,
    )

    if name == "pinecone":
        return PineconeAdapter()
    if name == "elastic":
        return ElasticVectorAdapter()
    return WeaviateAdapter()


def write_to_target(_doc: dict, _tenant: str | None = None) -> None:
    """Placeholder for target write logic.

    Intentionally no-op for now. Tests may monkeypatch this to simulate
    success/failure. Real implementations should index documents to the target.
    """
    return None
