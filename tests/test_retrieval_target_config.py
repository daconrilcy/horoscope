"""Tests pour la configuration des backends de récupération.

Ce module teste la validation et la gestion des configurations de backends cibles pour les systèmes
de récupération.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.services import retrieval_target as rtarget


def test_invalid_target_backend_raises(monkeypatch):
    """Teste qu'une erreur ValueError est levée pour un backend cible invalide.

    Vérifie que le système refuse de créer un adaptateur pour un backend qui n'existe pas dans la
    configuration.
    """
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "doesnotexist")
    with pytest.raises(ValueError):
        rtarget.get_target_adapter()


def test_get_target_backend_name_default(monkeypatch):
    """Teste que le nom du backend par défaut.

    Teste que le nom du backend par défaut est retourné quand aucune variable n'est définie.
    """
    monkeypatch.delenv("RETRIEVAL_TARGET_BACKEND", raising=False)
    monkeypatch.delenv("RETRIEVAL_MIGRATION_TARGET", raising=False)
    assert rtarget.get_target_backend_name() == "weaviate"


def test_get_target_backend_name_from_env(monkeypatch):
    """Teste que le nom du backend est lu depuis les variables d'environnement."""
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "pinecone")
    assert rtarget.get_target_backend_name() == "pinecone"

    monkeypatch.delenv("RETRIEVAL_TARGET_BACKEND", raising=False)
    monkeypatch.setenv("RETRIEVAL_MIGRATION_TARGET", "elastic")
    assert rtarget.get_target_backend_name() == "elastic"


def test_get_target_backend_name_case_insensitive(monkeypatch):
    """Teste que le nom du backend est converti en minuscules."""
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "WEAVIATE")
    assert rtarget.get_target_backend_name() == "weaviate"


def test_get_target_adapter_weaviate(monkeypatch):
    """Teste la création d'un adaptateur Weaviate."""
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "weaviate")
    adapter = rtarget.get_target_adapter()
    assert adapter is not None
    # Vérifier que c'est bien un adaptateur Weaviate
    assert hasattr(adapter, "search")


def test_get_target_adapter_pinecone(monkeypatch):
    """Teste la création d'un adaptateur Pinecone."""
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "pinecone")
    adapter = rtarget.get_target_adapter()
    assert adapter is not None
    # Vérifier que c'est bien un adaptateur Pinecone
    assert hasattr(adapter, "search")


def test_get_target_adapter_elastic(monkeypatch):
    """Teste la création d'un adaptateur Elastic."""
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "elastic")
    adapter = rtarget.get_target_adapter()
    assert adapter is not None
    # Vérifier que c'est bien un adaptateur Elastic
    assert hasattr(adapter, "search")


def test_write_to_target_noop():
    """Teste que write_to_target est une fonction no-op."""
    # Cette fonction ne devrait pas lever d'exception
    rtarget.write_to_target({"test": "document"}, "test_tenant")


def test_safe_write_to_target_success(monkeypatch):
    """Teste l'écriture sécurisée vers le backend cible en cas de succès."""
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "weaviate")

    # Mock de write_to_target pour simuler un succès
    with patch("backend.services.retrieval_target.write_to_target") as mock_write:
        rtarget.safe_write_to_target({"test": "document"}, "test_tenant")

        # Vérifier que write_to_target a été appelé
        mock_write.assert_called_once_with({"test": "document"}, "test_tenant")


def test_safe_write_to_target_failure(monkeypatch):
    """Teste l'écriture sécurisée vers le backend cible en cas d'échec."""
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "weaviate")

    # Mock de write_to_target pour simuler un échec
    with patch("backend.services.retrieval_target.write_to_target") as mock_write:
        mock_write.side_effect = Exception("Backend error")

        # Ne devrait pas lever d'exception
        rtarget.safe_write_to_target({"test": "document"}, "test_tenant")

        # Vérifier que write_to_target a été appelé
        mock_write.assert_called_once_with({"test": "document"}, "test_tenant")
