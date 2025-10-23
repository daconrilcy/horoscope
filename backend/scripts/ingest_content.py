"""
Script d'ingestion de contenus pour l'index de recherche.

Ce script lit un fichier JSON de snippets textuels et les indexe via le
`Retriever` (qui utilise un magasin vectoriel minimal). Il est conçu pour
fonctionner sans dépendances lourdes grâce aux fallbacks d'embedder.

Format attendu du JSON: dictionnaire {id -> {"id": str, "text": str, ...}}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Permet l'exécution du script en direct (python backend/scripts/ingest_content.py)
SYS_ROOT = Path(__file__).resolve().parents[2]
if str(SYS_ROOT) not in sys.path:
    sys.path.append(str(SYS_ROOT))

from backend.domain.retrieval_types import Document  # noqa: E402
from backend.domain.retriever import Retriever  # noqa: E402


def _load_documents(path: str) -> list[Document]:
    """
    Charge les snippets depuis `path` et construit des `Document`.

    Retourne une liste vide si le fichier n'existe pas.
    """
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    docs: list[Document] = []
    if isinstance(raw, dict):
        for key, val in raw.items():
            if not isinstance(val, dict):
                continue
            text = val.get("text", "")
            if not text:
                continue
            doc_id = val.get("id") or key
            docs.append(Document(id=str(doc_id), text=str(text)))
    return docs


def main() -> None:
    """Point d'entrée: lit le JSON et indexe les documents."""
    parser = argparse.ArgumentParser(
        description="Ingestion de contenus JSON vers l'index"
    )
    parser.add_argument(
        "--path",
        type=str,
        default=os.path.join("backend", "infra", "content.json"),
        help="Chemin du fichier JSON de contenus",
    )
    args = parser.parse_args()

    docs = _load_documents(args.path)
    if not docs:
        print(f"[ingest] aucun document chargé depuis {args.path}")
        return

    retriever = Retriever()
    n = retriever.index(docs)
    print(f"[ingest] indexés: {n} documents depuis {args.path}")
