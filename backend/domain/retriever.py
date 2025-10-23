"""Service de récupération de documents avec recherche vectorielle.

Ce module implémente le service de récupération de documents utilisant un store vectoriel FAISS pour
l'indexation et la recherche sémantique.
"""

from __future__ import annotations

from backend.domain.retrieval_types import Document, Query, ScoredDocument
from backend.infra.vecstores.faiss_store import FAISSVectorStore


class Retriever:
    """Service de récupération de documents avec recherche vectorielle.

    Fournit une interface simplifiée pour l'indexation et la recherche de documents utilisant un
    store vectoriel FAISS.
    """

    def __init__(self, store: FAISSVectorStore | None = None) -> None:
        """Initialise le service de récupération.

        Args:
            store: Store vectoriel à utiliser (FAISS par défaut).
        """
        self.store = store or FAISSVectorStore()

    def index(self, docs: list[Document]) -> int:
        """Indexe une liste de documents pour la recherche.

        Args:
            docs: Liste des documents à indexer.

        Returns:
            int: Nombre de documents indexés.
        """
        return self.store.index(docs)

    def query(self, q: Query) -> list[ScoredDocument]:
        """Recherche des documents similaires à une requête.

        Args:
            q: Requête de recherche avec texte et nombre de résultats.

        Returns:
            list[ScoredDocument]: Liste des documents trouvés avec scores.
        """
        return self.store.search(q)
