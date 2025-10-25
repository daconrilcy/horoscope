"""Tests unitaires pour l'enqueue post-commit (API→workers).

Vérifie que les actions enregistrées via `enqueue_task_after_commit` ne sont
exécutées qu'après un commit, et jamais après un rollback.
"""

from __future__ import annotations

import contextlib
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.infra.ops.post_commit import register_action_after_commit


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    return Session(bind=engine)


def test_register_action_runs_after_commit(monkeypatch):
    """Exécute l'action après commit et pas avant."""
    ran: dict[str, Any] = {"x": 0}

    def action() -> None:
        ran["x"] += 1

    s = _make_session()
    register_action_after_commit(s, action)
    # Avant commit: rien ne s'exécute
    assert ran["x"] == 0
    with contextlib.suppress(Exception):
        s.commit()
    # Après commit: l'action est exécutée
    assert ran["x"] == 1


def test_register_action_cleared_on_rollback():
    """Purge les actions sur rollback et ne les exécute pas ensuite."""
    ran: dict[str, int] = {"x": 0}

    def action() -> None:
        ran["x"] += 1

    s = _make_session()
    register_action_after_commit(s, action)
    # nested tx + savepoint
    s.begin()
    s.execute(text("SELECT 1"))
    s.rollback()  # rollback savepoint
    # Toujours rien
    assert ran["x"] == 0
    # L'action a été purgée suite au rollback; un commit ultérieur ne la joue pas
    with contextlib.suppress(Exception):
        s.commit()
    assert ran["x"] == 0
