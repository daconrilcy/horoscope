"""
Types de données pour le système de récupération de documents.

Ce module définit les modèles Pydantic pour les documents, requêtes et résultats de recherche avec
scores de similarité.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    """
    Modèle de document avec métadonnées.

    Représente un document avec son identifiant, contenu textuel et métadonnées optionnelles.
    """

    id: str
    text: str
    meta: dict[str, Any] = Field(default_factory=dict)


class Query(BaseModel):
    """
    Modèle de requête de recherche.

    Représente une requête de recherche avec le texte à rechercher et le nombre de résultats
    souhaités.
    """

    text: str
    k: int = 5


class ScoredDocument(BaseModel):
    """
    Modèle de document avec score de similarité.

    Représente un document de résultat avec son score de similarité par rapport à la requête de
    recherche.
    """

    doc: Document
    score: float
