"""
Script: scripts/check_cutover_criteria.py
Objet : Vérifier les critères de cutover à partir d'artefacts locaux.

Utilisation:
  python scripts/check_cutover_criteria.py --bench-json artifacts/bench/<ts>_<adapter>.json --agreement 0.9 --p95 200

Notes:
  - Ce script lit un JSON de bench (p50/p95/QPS/sha), compare p95 au seuil,
    et accepte un accord minimal attendu (agreement@5) passé en paramètre.
  - Pour `agreement@5`, ce script n'interroge pas Prometheus; passez un
    `--agreement-observed` si vous l'avez mesuré (shadow-read).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench-json", type=str, required=True)
    parser.add_argument("--p95", type=float, default=200.0)
    parser.add_argument("--agreement", type=float, default=0.9)
    parser.add_argument("--agreement-observed", type=float, default=None)
    args = parser.parse_args()

    path = Path(args.bench_json)
    if not path.exists():
        print(f"bench json not found: {path}")
        sys.exit(2)
    data = json.loads(path.read_text(encoding="utf-8"))
    p95_ms = float(data.get("p95_ms", 1e9))
    ok_p95 = p95_ms < args.p95

    ok_agreement = True
    if args.agreement_observed is not None:
        ok_agreement = float(args.agreement_observed) >= args.agreement

    if ok_p95 and ok_agreement:
        print("criteria OK")
        sys.exit(0)
    print(f"criteria FAILED: p95_ms={p95_ms} (<{args.p95}) agreement_ok={ok_agreement}")
    sys.exit(1)


if __name__ == "__main__":
    main()

