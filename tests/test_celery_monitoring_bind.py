"""
Tests pour la liaison des signaux Celery.

Ce module teste que la liaison des signaux Celery ne casse pas
le bootstrap de l'application et fonctionne correctement.

But: Vérifier que le bind des signaux Celery ne casse pas le bootstrap.
- No-op si instrumentation absente
- Pas d'exception au bind.
"""

from __future__ import annotations

from importlib import reload

from backend.app import celery_app


def test_celery_signals_bind_bootstrap_ok(monkeypatch) -> None:
    """Teste que la liaison des signaux Celery ne casse pas le bootstrap."""
    # Évite effets de bord: reload le module pour (re)déclencher le bind

    reload(celery_app)
    # Si on arrive ici sans exception, cest suffisant pour ce test fumée
    assert hasattr(celery_app, "celery_app")
