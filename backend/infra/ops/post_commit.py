"""Post-commit enqueue helpers for API→workers handoff.

Ce module fournit des utilitaires pour déclencher des actions (ex: envoi de tâches
Celery) uniquement après qu'une transaction SQLAlchemy ait été effectivement
commitée. Il évite d'enqueuer des jobs si la transaction est rollback.
"""

from __future__ import annotations

import contextlib
import functools
from collections.abc import Callable

from sqlalchemy import event
from sqlalchemy.orm import Session

from backend.app.celery_app import celery_app

try:
    from prometheus_client import Counter as _PromCounter  # type: ignore

    POSTCOMMIT_ENQUEUE_TOTAL = _PromCounter(
        "postcommit_enqueue_total",
        "Post-commit enqueue outcomes",
        ["result"],
    )
except Exception:  # pragma: no cover
    POSTCOMMIT_ENQUEUE_TOTAL = None  # type: ignore[assignment]

_ACTIONS_KEY = "_post_commit_actions"


def _ensure_action_list(session: Session) -> list[Callable[[], None]]:
    """Ensure action list container exists on session.info and return it."""
    actions = session.info.get(_ACTIONS_KEY)
    if actions is None:
        actions = []
        session.info[_ACTIONS_KEY] = actions
        _bind_session_events(session)
    return actions


def _bind_session_events(session: Session) -> None:
    """Bind commit/rollback events once for the given session instance."""
    # Guard to avoid double binding on same instance
    if session.info.get("_post_commit_bound"):
        return
    session.info["_post_commit_bound"] = True

    # Wrap rollback to always clear actions, even when SQLA doesn't fire events
    if not session.info.get("_post_commit_rb_wrapped"):
        session.info["_post_commit_rb_wrapped"] = True
        _orig_rollback = session.rollback

        def _wrapped_rollback(*args, **kwargs):  # type: ignore[no-untyped-def]
            try:
                return _orig_rollback(*args, **kwargs)
            finally:
                session.info[_ACTIONS_KEY] = []

        session.rollback = _wrapped_rollback  # type: ignore[assignment]

    @event.listens_for(session, "after_commit")
    def _after_commit(_session: Session) -> None:
        actions = list(_session.info.get(_ACTIONS_KEY, []) or [])
        _session.info[_ACTIONS_KEY] = []
        for action in actions:
            # Pas d'exception remontée ici: l'envoi post-commit ne doit pas casser le flux API
            # Les tâches Celery pourront être retriées côté broker si besoin.
            with contextlib.suppress(Exception):
                action()
                if POSTCOMMIT_ENQUEUE_TOTAL:
                    POSTCOMMIT_ENQUEUE_TOTAL.labels(result="enqueued").inc()

    @event.listens_for(session, "after_rollback")
    def _after_rollback(_session: Session) -> None:
        # Purge les actions planifiées si la transaction est rollback
        _session.info[_ACTIONS_KEY] = []
        if POSTCOMMIT_ENQUEUE_TOTAL:
            POSTCOMMIT_ENQUEUE_TOTAL.labels(result="rolled_back").inc()


def register_action_after_commit(
    session: Session,
    func: Callable[..., None],
    *args,
    **kwargs,
) -> None:
    """Register an arbitrary callable to run after a successful commit.

    La fonction est stockée dans la session et exécutée lors de l'évènement
    `after_commit`. En cas de rollback, elle est oubliée.
    """
    bound = functools.partial(func, *args, **kwargs)
    _ensure_action_list(session).append(bound)


def enqueue_task_after_commit(
    session: Session,
    task_name: str,
    *args,
    queue: str | None = None,
    countdown: int | None = None,
    **kwargs,
) -> None:
    """Enqueue a Celery task only after the current transaction commits.

    Args:
        session: Session SQLAlchemy concernée.
        task_name: Nom pleinement qualifié de la tâche Celery (ex: "backend.tasks.render_pdf").
        args: Arguments positionnels de la tâche.
        queue: Nom de la queue cible (optionnel).
        countdown: Délai (secondes) avant exécution (optionnel).
        kwargs: Arguments nommés de la tâche.
    """

    def _send_task() -> None:
        opts: dict[str, object] = {}
        if queue:
            opts["queue"] = queue
        if countdown is not None:
            opts["countdown"] = countdown
        # Ne jamais lever côté API: la transaction est déjà commit, la livraison
        # peut être relancée par un mécanisme de retry externe si besoin.
        with contextlib.suppress(Exception):
            celery_app.send_task(task_name, args=args, kwargs=kwargs, **opts)
            if POSTCOMMIT_ENQUEUE_TOTAL:
                POSTCOMMIT_ENQUEUE_TOTAL.labels(result="enqueued").inc()

    register_action_after_commit(session, _send_task)


__all__ = [
    "enqueue_task_after_commit",
    "register_action_after_commit",
]
