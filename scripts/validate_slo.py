from __future__ import annotations

"""Validate slo.yaml against a minimal JSON schema without extra deps.

Exit code 0 on success, 1 on invalid file/structure.
"""

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


def validate_file(path: Path) -> bool:
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

    for idx, slo in enumerate(data["slos" ]):
        if not isinstance(slo, dict):
            _fail(f"slo[{idx}] must be an object")
        _require_keys(slo, ["id", "name", "objective", "window"], f"slo[{idx}]")
        alerts = slo.get("alerts", [])
        if alerts is not None:
            if not isinstance(alerts, list):
                _fail(f"slo[{idx}].alerts must be an array if present")
            for j, a in enumerate(alerts):
                if not isinstance(a, dict):
                    _fail(f"slo[{idx}].alerts[{j}] must be an object")
                _require_keys(a, ["name", "expr", "severity"], f"slo[{idx}].alerts[{j}]")
    return True


def main() -> None:
    path = Path("slo.yaml")
    ok = validate_file(path)
    if not ok:
        raise SystemExit(1)
    print("slo.yaml OK")


if __name__ == "__main__":  # pragma: no cover
    main()

