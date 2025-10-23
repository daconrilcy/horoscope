"""
Script de drill de rollback vers FAISS uniquement.

Ce script effectue un drill de rollback (dry-run ou application) et ajoute un journal NDJSON pour
l'audit des opérations de rollback.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path


def _update_env_lines(lines: list[str]) -> list[str]:
    """Return updated .env lines enforcing FAISS-only and flags OFF."""
    wanted = {
        "FF_RETRIEVAL_DUAL_WRITE": "OFF",
        "FF_RETRIEVAL_SHADOW_READ": "OFF",
        "RETRIEVAL_BACKEND": "faiss",
    }
    out: list[str] = []
    seen: set[str] = set()
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            out.append(ln)
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        if k in wanted:
            out.append(f"{k}={wanted[k]}\n")
            seen.add(k)
        else:
            out.append(ln)
    for k, v in wanted.items():
        if k not in seen:
            out.append(f"{k}={v}\n")
    return out


def main() -> int:
    """Perform rollback drill (dry-run or apply) and append NDJSON journal."""
    parser = argparse.ArgumentParser(description="Rollback retrieval to FAISS-only")
    parser.add_argument("--env-file", type=str, default=".env")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--operator",
        type=str,
        default=os.getenv("USER") or os.getenv("USERNAME") or "operator",
    )
    parser.add_argument("--reason", type=str, default="drill")
    args = parser.parse_args()

    t0 = time.perf_counter()
    env_path = Path(args.env_file)
    changes = {
        "FF_RETRIEVAL_DUAL_WRITE": "OFF",
        "FF_RETRIEVAL_SHADOW_READ": "OFF",
        "RETRIEVAL_BACKEND": "faiss",
    }
    applied = False
    if args.apply and env_path.exists():
        # backup then update in place
        bak = env_path.with_suffix(env_path.suffix + ".bak")
        shutil.copyfile(env_path, bak)
        data = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
        updated = _update_env_lines(data)
        env_path.write_text("".join(updated), encoding="utf-8")
        applied = True

    # append NDJSON journal
    log = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "operator": args.operator,
        "env_file": str(env_path),
        "apply": bool(args.apply),
        "result": "success",
        "duration_s": round(time.perf_counter() - t0, 3),
        "changes": changes,
        "notes": args.reason,
    }
    out = Path("artifacts/rollback_drill_log.ndjson")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(log, ensure_ascii=False) + "\n")

    print(("[dry-run]" if not applied else "[apply]"), json.dumps(changes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
