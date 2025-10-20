from __future__ import annotations

"""Validate slo.yaml against a minimal JSON schema without extra deps.

Exit code 0 on success, 1 on invalid file/structure.

Strict mode (--strict):
- Enforce unique alert identifiers (use alert 'name' as ID)
- Validate objective targets (ratios in (0,1], durations/costs >0)
- Ensure each alert references a known metric (best‑effort)
"""

import argparse
import json
import sys
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
    # Chat metrics
    "chat_latency_seconds_bucket",
    # LLM budgets/costs
    "llm_cost_usd_total",
}


def _expr_has_known_metric(expr: str) -> bool:
    return any(m in expr for m in KNOWN_METRICS)


def validate_file(path: Path, strict: bool = False) -> bool:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except Exception as exc:  # pragma: no cover - defensive
        _fail(f"invalid JSON: {exc}")
        return False

    if not isinstance(data, dict):
        _fail("root must be an object")
    _require_keys(data, ["service", "version", "slos"], "root")

    if not isinstance(data["slos"], list) or not data["slos"]:
        _fail("'slos' must be a non-empty array")

    seen_alert_names: set[str] = set()
    for idx, slo in enumerate(data["slos" ]):
        if not isinstance(slo, dict):
            _fail(f"slo[{idx}] must be an object")
        _require_keys(slo, ["id", "name", "objective", "window"], f"slo[{idx}]")
        # Strict target validation
        if strict:
            if "target" in slo:
                try:
                    t = float(slo["target"])
                except Exception:
                    _fail(f"slo[{idx}].target must be numeric")
                if not (0.0 < t <= 1.0):
                    _fail(f"slo[{idx}].target must be in (0,1]")
            if "target_seconds" in slo:
                try:
                    ts = float(slo["target_seconds"])
                except Exception:
                    _fail(f"slo[{idx}].target_seconds must be numeric")
                if not (ts > 0):
                    _fail(f"slo[{idx}].target_seconds must be > 0")
            if "target_usd" in slo:
                try:
                    usd = float(slo["target_usd"])
                except Exception:
                    _fail(f"slo[{idx}].target_usd must be numeric")
                if not (usd > 0):
                    _fail(f"slo[{idx}].target_usd must be > 0")
        alerts = slo.get("alerts", [])
        if alerts is not None:
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
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Enable strict validation")
    args = parser.parse_args()
    path = Path("slo.yaml")
    ok = validate_file(path, strict=args.strict)
    if not ok:
        raise SystemExit(1)
    print("slo.yaml OK")


if __name__ == "__main__":  # pragma: no cover
    main()
