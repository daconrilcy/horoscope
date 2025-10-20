"""
But: Vérifier que le bind des signaux Celery ne casse pas le bootstrap.
- No-op si instrumentation absente
- Pas d’exception au bind
"""

from __future__ import annotations

from importlib import reload


def test_celery_signals_bind_bootstrap_ok(monkeypatch) -> None:
    # Évite effets de bord: reload le module pour (re)déclencher le bind
    import backend.app.celery_app as celery_app

    reload(celery_app)
    # Si on arrive ici sans exception, c’est suffisant pour ce test fumée
    assert hasattr(celery_app, "celery_app")

