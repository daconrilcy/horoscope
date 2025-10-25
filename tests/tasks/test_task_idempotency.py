"""Tests unitaires pour l'idempotence des tâches workers."""

from __future__ import annotations

from backend.infra.ops.idempotency import (
    canonical_task_key,
    idempotency_store,
    idempotent_task,
    make_idem_key,
)


def test_idempotent_task_decorator_duplicate(monkeypatch):
    """Vérifie que le décorateur renvoie 'dup' sur duplication et n'exécute pas la fonction."""
    calls = {"n": 0}

    @idempotent_task(lambda x: make_idem_key("unit", x), ttl_seconds=60, on_duplicate_return="dup")
    def do_work(x: str) -> str:
        calls["n"] += 1
        return f"ok:{x}"

    # Première exécution: passe
    assert do_work("A") == "ok:A"
    # Forcer store à refuser l'acquisition pour simuler doublon
    key = make_idem_key("unit", "A")
    assert not idempotency_store.acquire(key, ttl=60)
    # Deuxième exécution: renvoie la valeur duplicate et n'appelle pas la fonction
    assert do_work("A") == "dup"
    # Une seule exécution réelle
    assert calls["n"] == 1


def test_canonical_key_is_order_invariant():
    """Vérifie que la clé canonique est indépendante de l'ordre des dicts/kwargs."""
    k1 = canonical_task_key("t", (1, {"a": 1, "b": 2}), {"x": {"k": 3, "j": 4}})
    k2 = canonical_task_key("t", (1, {"b": 2, "a": 1}), {"x": {"j": 4, "k": 3}})
    assert k1 == k2


def test_concurrent_dedup_simulated(monkeypatch):
    """Simule deux exécutions quasi simultanées: une seule passe, l'autre dedup."""
    calls = {"n": 0}

    # Force le store à accepter la première et refuser la seconde
    state = {"first": True}

    def fake_acquire(key: str, ttl: int | None = None) -> bool:  # type: ignore[unused-argument]
        if state["first"]:
            state["first"] = False
            return True
        return False

    monkeypatch.setattr(idempotency_store, "acquire", fake_acquire)

    @idempotent_task(lambda x: make_idem_key("unit", x), ttl_seconds=60, on_duplicate_return="dup")
    def do_work(x: str) -> str:
        calls["n"] += 1
        return f"ok:{x}"

    r1 = do_work("A")
    r2 = do_work("A")
    assert r1 == "ok:A"
    assert r2 == "dup"
    assert calls["n"] == 1
