"""
Monitor SLO burn-rate and exit non-zero if above threshold.

Ce script surveille le burn-rate SLO et sort avec un code non-zéro si
le seuil d'abort est dépassé, avec support pour les requêtes Prometheus.

Usage:
  python scripts/slo_burn_monitor.py --window 900 --abort-threshold 2.0 \
    --target-error 0.01 --prom-url $PROM_QUERY_URL

If --prom-url is provided, queries Prometheus for a simple 5xx ratio as an
example. Otherwise, prints an info line and exits 0 (no abort).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from typing import Any


def _query_prom_ratio(prom_url: str, window: int) -> float | None:
    expr = (
        f'sum(rate(http_requests_total{{status=~"5.."}}[{window}s])) / '
        f"clamp_min(sum(rate(http_requests_total[{window}s])), 1)"
    )
    url = f"{prom_url.rstrip('/')}/api/v1/query?query={expr}"
    try:
        res = subprocess.run(
            ["curl", "-sS", "-m", "3", url],
            check=True,
            capture_output=True,
            text=True,
        )
        data: dict[str, Any] = json.loads(res.stdout)
        if data.get("status") != "success":
            return None
        results = data.get("data", {}).get("result", [])
        if not results:
            return 0.0
        # Combine by summing values; here we just take the first for simplicity
        try:
            val = float(results[0].get("value", [0, "0"])[1])
        except Exception:
            val = None
        return val
    except Exception:
        return None


def main() -> int:
    """
    Point d'entrée principal pour le monitoring du burn-rate SLO.

    Returns:
        int: Code de sortie (0 si OK, 1 si seuil dépassé).
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", type=int, default=900)
    parser.add_argument("--abort-threshold", type=float, default=2.0)
    parser.add_argument("--target-error", type=float, default=0.01)
    parser.add_argument(
        "--prom-url", type=str, default=os.getenv("PROM_QUERY_URL") or ""
    )
    args = parser.parse_args()

    # error_rate ≈ 5xx_ratio; burn = error_rate / target_error
    prom_url = args.prom_url.strip()
    if not prom_url:
        print("no prom-url provided; assuming burn-rate OK")
        return 0
    current = _query_prom_ratio(prom_url, args.window)
    if current is None:
        print("unable to query prom; assuming OK")
        return 0
    target = max(1e-9, float(args.target_error))
    burn = float(current) / target
    print(f"burn_rate={burn:.3f} current_error={current:.6f} target_error={target:.6f}")
    return 1 if burn > float(args.abort_threshold) else 0


if __name__ == "__main__":
    raise SystemExit(main())
