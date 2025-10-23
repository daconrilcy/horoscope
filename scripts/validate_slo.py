"""
Validate slo.yaml against a minimal JSON schema without extra deps.

Ce script valide slo.yaml contre un schéma JSON minimal sans dépendances
externes, avec mode strict pour la validation des objectifs et alertes.

Exit code 0 on success, 1 on invalid file/structure.

Strict mode (--strict):
- Enforce unique alert identifiers (use alert 'name' as ID)
- Validate objective targets (ratios in (0,1], durations/costs >0)
- Ensure each alert references a known metric (best-effort)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _fail(msg: str) -> None:
    print(f"SLO validation error: {msg}")
    raise SystemExit(1)


def _require_keys(obj: dict[str, Any], keys: list[str], ctx: str) -> None:
    for k in keys:
        if k not in obj:
            _fail(f"missing key '{k}' in {ctx}")


KNOWN_METRICS = {
    # HTTP/API
    "http_requests_total",
    "http_server_requests_seconds_bucket",
    # Chat metrics
    "chat_latency_seconds_bucket",
    # LLM budgets/costs
    "llm_cost_usd_total",
}


def _expr_has_known_metric(expr: str) -> bool:
    return any(m in expr for m in KNOWN_METRICS)


def _validate_root_structure(data: dict[str, Any]) -> None:
    """
    Vérifier la structure racine du fichier SLO.

    Args:
        data: Données JSON chargées.
    """
    if not isinstance(data, dict):
        _fail("root must be an object")
    _require_keys(data, ["service", "version", "slos"], "root")

    if not isinstance(data["slos"], list) or not data["slos"]:
        _fail("'slos' must be a non-empty array")


def _validate_target_ratio(slo: dict[str, Any], idx: int) -> None:
    """
    Vérifier la cible ratio.

    Args:
        slo: Configuration SLO.
        idx: Index du SLO.
    """
    if "target" not in slo:
        return
    try:
        t = float(slo["target"])
    except Exception:
        _fail(f"slo[{idx}].target must be numeric")
    if not (0.0 < t <= 1.0):
        _fail(f"slo[{idx}].target must be in (0,1]")


def _validate_target_seconds(slo: dict[str, Any], idx: int) -> None:
    """
    Vérifier la cible en secondes.

    Args:
        slo: Configuration SLO.
        idx: Index du SLO.
    """
    if "target_seconds" not in slo:
        return
    try:
        ts = float(slo["target_seconds"])
    except Exception:
        _fail(f"slo[{idx}].target_seconds must be numeric")
    if not (ts > 0):
        _fail(f"slo[{idx}].target_seconds must be > 0")


def _validate_target_usd(slo: dict[str, Any], idx: int) -> None:
    """
    Vérifier la cible en USD.

    Args:
        slo: Configuration SLO.
        idx: Index du SLO.
    """
    if "target_usd" not in slo:
        return
    try:
        usd = float(slo["target_usd"])
    except Exception:
        _fail(f"slo[{idx}].target_usd must be numeric")
    if not (usd > 0):
        _fail(f"slo[{idx}].target_usd must be > 0")


def _validate_target_values(slo: dict[str, Any], idx: int, strict: bool) -> None:
    """
    Vérifier les valeurs des cibles SLO.

    Args:
        slo: Configuration SLO.
        idx: Index du SLO.
        strict: Si True, effectue des vérifications strictes.
    """
    if not strict:
        return

    _validate_target_ratio(slo, idx)
    _validate_target_seconds(slo, idx)
    _validate_target_usd(slo, idx)


def _validate_alerts(
    slo: dict[str, Any], idx: int, strict: bool, seen_alert_names: set[str]
) -> None:
    """
    Vérifier les alertes d'un SLO.

    Args:
        slo: Configuration SLO.
        idx: Index du SLO.
        strict: Si True, effectue des vérifications strictes.
        seen_alert_names: Noms d'alertes déjà vus.
    """
    alerts = slo.get("alerts", [])
    if alerts is None:
        return

    if not isinstance(alerts, list):
        _fail(f"slo[{idx}].alerts must be an array if present")

    for j, a in enumerate(alerts):
        if not isinstance(a, dict):
            _fail(f"slo[{idx}].alerts[{j}] must be an object")
        _require_keys(a, ["name", "expr", "severity"], f"slo[{idx}].alerts[{j}]")

        if strict:
            name = str(a.get("name"))
            if name in seen_alert_names:
                _fail(f"duplicate alert name '{name}'")
            seen_alert_names.add(name)

            expr = str(a.get("expr"))
            if not _expr_has_known_metric(expr):
                _fail(f"alert '{name}' expression references unknown metrics")


def validate_file(path: Path, strict: bool = False) -> bool:
    """
    Validate an SLO file against JSON schema.

    Args:
        path: Chemin vers le fichier SLO à valider.
        strict: Si True, effectue des vérifications strictes.

    Returns:
        bool: True si le fichier est valide, False sinon.
    """
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except Exception as exc:  # pragma: no cover - defensive
        _fail(f"invalid JSON: {exc}")
        return False

    _validate_root_structure(data)

    seen_alert_names: set[str] = set()
    for idx, slo in enumerate(data["slos"]):
        if not isinstance(slo, dict):
            _fail(f"slo[{idx}] must be an object")
        _require_keys(slo, ["id", "name", "objective", "window"], f"slo[{idx}]")

        _validate_target_values(slo, idx, strict)
        _validate_alerts(slo, idx, strict, seen_alert_names)

    return True


def main() -> None:
    """
    Point d'entrée principal pour la validation des fichiers SLO.

    Valide la structure et le contenu des fichiers de configuration SLO contre un schéma JSON
    minimal.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict", action="store_true", help="Enable strict validation"
    )
    args = parser.parse_args()
    path = Path("slo.yaml")
    ok = validate_file(path, strict=args.strict)
    if not ok:
        raise SystemExit(1)
    print("slo.yaml OK")


if __name__ == "__main__":  # pragma: no cover
    main()
