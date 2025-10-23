"""
Generate SLO report (Markdown/JSON) from slo.yaml and optional metrics.

Ce script génère un rapport SLO à partir de slo.yaml et de métriques optionnelles,
avec évaluation des violations et export en formats Markdown et JSON.

Usage:
  python -m scripts.slo_report --output-dir artifacts/slo --month 2025-10 \
      --json-out artifacts/slo/slo_report.json \
      --metrics artifacts/slo/metrics_sample.json --fail-on-breach

Notes:
- slo.yaml is JSON-compatible YAML to avoid extra dependencies.
- Dashboard base URL can be provided via GRAFANA_DASHBOARD_URL.
"""

from __future__ import annotations

import argparse
import calendar
import json
import math
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from backend.core.constants import (
    SCRIPT_BUDGET_MAX_PERCENTAGE,
    SCRIPT_DATE_FORMAT_LENGTH,
    SCRIPT_SLO_BREACH_THRESHOLD_1H,
    SCRIPT_SLO_BREACH_THRESHOLD_6H,
)


def _load_slo_config(path: Path) -> dict:
    """Load SLO configuration (JSON-compatible YAML)."""
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def _month_label(ym: str | None) -> tuple[int, int, str]:
    """Return (year, month, label) for the given YYYY-MM or current month."""
    if ym and len(ym) == SCRIPT_DATE_FORMAT_LENGTH and ym[4] == "-":
        y = int(ym[:4])
        m = int(ym[5:7])
    else:
        today = date.today()
        y, m = today.year, today.month
    label = f"{y}-{m:02d} ({calendar.month_name[m]})"
    return y, m, label


def _dashboard_link(base: str | None, slo_id: str) -> str:
    if not base:
        return "(dashboard: set GRAFANA_DASHBOARD_URL)"
    # naive anchor by SLO id (adjust to actual dashboard structure)
    return f"{base}?var-slo={slo_id}"


def _prom_top_routes_5xx(base: str | None) -> list[tuple[str, float]]:
    """Query Prometheus for top 3 routes with 5xx (avg rate over 5m)."""
    if not base:
        return []
    prom = os.getenv("PROM_QUERY_URL") or base  # allow dedicated read-only URL
    query = 'topk(3, sum(rate(http_requests_total{status=~"5.."}[5m])) by (route))'
    url = f"{prom}/api/v1/query?query={query}"
    try:
        res = subprocess.run(
            ["curl", "-sS", "-m", "3", url],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(res.stdout)
        if data.get("status") != "success":
            return []
        results = data.get("data", {}).get("result", [])
        out: list[tuple[str, float]] = []
        for r in results:
            route = r.get("metric", {}).get("route", "")
            try:
                val = float(r.get("value", [0, "0"])[1])
            except Exception:
                val = 0.0
            out.append((route, val))
        return out
    except Exception:
        return []


def _status_icon(ok: bool | None) -> str:
    if ok is True:
        return "✅"
    if ok is False:
        return "❌"
    return "⚠️"


def _load_metrics(path: Path | None) -> dict:
    """
    Load optional synthetic metrics for breach evaluation.

    Expected format:
    {
      "endpoints": {
        "GET /chat/answer": {
          "p95": 0.28, "p99": 0.62, "error_rate": 0.003,
          "requests_5m": 200,
          "burn_rate_1h": 1.2, "burn_rate_6h": 0.8
        }
      }
    }
    """
    if path is None:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _endpoint_key(slo: dict[str, Any]) -> str:
    route = str(slo.get("route", ""))
    method = str(slo.get("method", "")).upper() if slo.get("method") else ""
    return f"{method} {route}".strip()


def _min_requests_window_for(
    slo: dict[str, Any], cfg: dict[str, Any]
) -> tuple[str, int]:
    """Return (window, min_requests) for gating low-traffic evaluations."""
    default_mrw = cfg.get("defaults", {}).get("min_requests_window") or {}
    mrw = (slo.get("min_requests_window") or default_mrw) if slo else default_mrw
    window = str(mrw.get("window", "5m"))
    try:
        min_requests = int(mrw.get("min_requests", 0))
    except Exception:
        min_requests = 0
    return window, min_requests


def _check_traffic_gating(
    slo: dict[str, Any], cfg: dict[str, Any], stats: dict[str, float]
) -> bool:
    """
    Vérifie si le trafic est suffisant pour l'évaluation.

    Args:
        slo: Configuration SLO.
        cfg: Configuration globale.
        stats: Statistiques de l'endpoint.

    Returns:
        bool: True si le trafic est trop faible.
    """
    _window, min_req = _min_requests_window_for(slo, cfg)
    req_cnt = 0
    for k in ("requests_window_count", "requests_5m"):
        if k in stats:
            try:
                req_cnt = int(stats[k])
            except Exception:
                req_cnt = 0
            break
    return min_req > 0 and req_cnt > 0 and req_cnt < min_req


def _check_latency_breach(
    slo: dict[str, Any], stats: dict[str, float], breaches: list[dict[str, Any]]
) -> None:
    """
    Vérifie les violations de latence.

    Args:
        slo: Configuration SLO.
        stats: Statistiques de l'endpoint.
        breaches: Liste des violations à modifier.
    """
    sid = str(slo.get("id", ""))
    name = str(slo.get("name", sid))

    if "target_p95_seconds" in slo:
        p95 = float(stats.get("p95", float("nan")))
        if not math.isnan(p95) and p95 > float(slo["target_p95_seconds"]):
            breaches.append(
                {
                    "id": sid,
                    "name": name,
                    "reason": f"p95 {p95:.3f}s > {float(slo['target_p95_seconds']):.3f}s",
                }
            )

    if "target_p99_seconds" in slo:
        p99 = float(stats.get("p99", float("nan")))
        if not math.isnan(p99) and p99 > float(slo["target_p99_seconds"]):
            breaches.append(
                {
                    "id": sid,
                    "name": name,
                    "reason": f"p99 {p99:.3f}s > {float(slo['target_p99_seconds']):.3f}s",
                }
            )


def _check_error_rate_breach(
    slo: dict[str, Any], stats: dict[str, float], breaches: list[dict[str, Any]]
) -> None:
    """
    Vérifie les violations de taux d'erreur.

    Args:
        slo: Configuration SLO.
        stats: Statistiques de l'endpoint.
        breaches: Liste des violations à modifier.
    """
    if "target_error_rate" not in slo:
        return

    sid = str(slo.get("id", ""))
    name = str(slo.get("name", sid))
    er = float(stats.get("error_rate", float("nan")))

    if not math.isnan(er) and er > float(slo["target_error_rate"]):
        breaches.append(
            {
                "id": sid,
                "name": name,
                "reason": f"error_rate {er:.4f} > {float(slo['target_error_rate']):.4f}",
            }
        )


def _check_freeze_policy(
    slo: dict[str, Any], stats: dict[str, float], breaches: list[dict[str, Any]]
) -> None:
    """
    Vérifie la politique de gel.

    Args:
        slo: Configuration SLO.
        stats: Statistiques de l'endpoint.
        breaches: Liste des violations à modifier.
    """
    br1h = float(stats.get("burn_rate_1h", float("nan")))
    br6h = float(stats.get("burn_rate_6h", float("nan")))

    if (
        not math.isnan(br1h)
        and not math.isnan(br6h)
        and br1h > SCRIPT_SLO_BREACH_THRESHOLD_1H
        and br6h > SCRIPT_SLO_BREACH_THRESHOLD_6H
    ):
        sid = str(slo.get("id", ""))
        name = str(slo.get("name", sid))
        breaches.append(
            {
                "id": f"policy_freeze_{sid}",
                "name": f"Freeze policy — {name}",
                "reason": (
                    f"burn_rate_1h={br1h:.2f} > {SCRIPT_SLO_BREACH_THRESHOLD_1H} AND "
                    f"burn_rate_6h={br6h:.2f} > {SCRIPT_SLO_BREACH_THRESHOLD_6H}"
                ),
            }
        )


def _check_budget_breach(slo: dict[str, Any], breaches: list[dict[str, Any]]) -> None:
    """
    Vérifie les violations de budget.

    Args:
        slo: Configuration SLO.
        breaches: Liste des violations à modifier.
    """
    if slo.get("id") != "llm_budget" or "target_usd" not in slo:
        return

    try:
        mtd_cost = float(os.getenv("LLM_BUDGET_MTD", "0") or 0)
    except Exception:
        mtd_cost = 0.0

    target = float(slo["target_usd"])
    if target > 0 and mtd_cost > target:
        sid = str(slo.get("id", ""))
        name = str(slo.get("name", sid))
        breaches.append(
            {
                "id": sid,
                "name": name,
                "reason": f"budget {mtd_cost:.2f}USD > {target:.2f}USD",
            }
        )


def evaluate_breaches(cfg: dict, metrics: dict) -> list[dict[str, Any]]:
    """
    Evaluate SLO breaches using optional synthetic metrics.

    Rules:
    - For endpoint latency SLOs: compare metrics[endpoint].p95/p99 to targets.
    - For endpoint error SLOs: compare metrics[endpoint].error_rate to target.
    - For budget: compare env LLM_BUDGET_MTD to target_usd.

    Returns list of breaches with {id, reason}.
    """
    breaches: list[dict[str, Any]] = []
    ep_stats: dict[str, dict[str, float]] = metrics.get("endpoints") or {}  # type: ignore[assignment]

    for slo in cfg.get("slos", []):
        key = _endpoint_key(slo)
        stats = ep_stats.get(key, {})
        low_traffic = _check_traffic_gating(slo, cfg, stats)

        if not low_traffic:
            _check_latency_breach(slo, stats, breaches)
            _check_error_rate_breach(slo, stats, breaches)
            _check_freeze_policy(slo, stats, breaches)

        _check_budget_breach(slo, breaches)

    return breaches


def _add_slo_header(lines: list[str], cfg: dict, label: str) -> None:
    """
    Ajoute l'en-tête du rapport SLO.

    Args:
        lines: Lignes du rapport à modifier.
        cfg: Configuration SLO.
        label: Libellé du mois.
    """
    lines.append(f"# SLO Report — {cfg.get('service', 'service')} — {label}\n\n")
    lines.append("## Summary\n\n")
    lines.append("- Version: " + str(cfg.get("version", 1)) + "\n")
    lines.append("- Owner: " + str(cfg.get("owner", "unknown")) + "\n\n")


def _add_slo_targets(lines: list[str], slo: dict[str, Any]) -> None:
    """
    Ajoute les cibles d'un SLO.

    Args:
        lines: Lignes du rapport à modifier.
        slo: Configuration SLO.
    """
    if "target" in slo:
        lines.append(f"- Target: {slo['target']}\n")
    if "target_seconds" in slo:
        lines.append(f"- Target seconds: {slo['target_seconds']}\n")
    if "rto_minutes" in slo:
        lines.append(f"- RTO minutes: {slo['rto_minutes']}\n")
    if "rpo_minutes" in slo:
        lines.append(f"- RPO minutes: {slo['rpo_minutes']}\n")


def _add_slo_budget(lines: list[str], slo: dict[str, Any]) -> None:
    """
    Ajoute les informations de budget d'un SLO.

    Args:
        lines: Lignes du rapport à modifier.
        slo: Configuration SLO.
    """
    if "target_usd" not in slo:
        return

    target = float(slo["target_usd"])
    try:
        mtd_cost = float(os.getenv("LLM_BUDGET_MTD", "0") or 0)
    except Exception:
        mtd_cost = 0.0
    used_pct = (mtd_cost / target * 100.0) if target > 0 else 0.0
    lines.append(f"- Target budget (USD): {target}\n")
    lines.append(f"- MTD cost (USD): {mtd_cost:.2f} ({used_pct:.1f}%)\n")


def _add_slo_status(lines: list[str], slo: dict[str, Any]) -> None:
    """
    Ajoute le statut d'un SLO.

    Args:
        lines: Lignes du rapport à modifier.
        slo: Configuration SLO.
    """
    status: bool | None = None
    if slo.get("id") == "llm_budget" and "target_usd" in slo:
        target = float(slo["target_usd"])
        try:
            mtd_cost = float(os.getenv("LLM_BUDGET_MTD", "0") or 0)
        except Exception:
            mtd_cost = 0.0
        used_pct = (mtd_cost / target * 100.0) if target > 0 else 0.0
        status = used_pct <= SCRIPT_BUDGET_MAX_PERCENTAGE
    lines.append(f"- Status: {_status_icon(status)}\n")


def _add_slo_alerts(lines: list[str], slo: dict[str, Any]) -> None:
    """
    Ajoute les alertes d'un SLO.

    Args:
        lines: Lignes du rapport à modifier.
        slo: Configuration SLO.
    """
    alerts = slo.get("alerts", [])
    if alerts:
        lines.append("- Alerts:\n")
        for a in alerts:
            lines.append(
                f"  - {a.get('name')}: {a.get('expr')} (sev={a.get('severity')})\n"
            )


def _add_slo_objectives(lines: list[str], cfg: dict, dash_base: str | None) -> None:
    """
    Ajoute la section des objectifs SLO.

    Args:
        lines: Lignes du rapport à modifier.
        cfg: Configuration SLO.
        dash_base: URL de base du dashboard.
    """
    lines.append("## Objectives\n\n")
    for slo in cfg.get("slos", []):
        name = slo.get("name") or slo.get("id")
        lines.append(f"### {name}\n\n")
        lines.append("- Objective: " + str(slo.get("objective", "")) + "\n")

        _add_slo_targets(lines, slo)
        _add_slo_budget(lines, slo)

        lines.append(f"- Window: {slo.get('window', '30d')}\n")
        lines.append(f"- Dashboard: {_dashboard_link(dash_base, slo.get('id', ''))}\n")

        _add_slo_status(lines, slo)
        _add_slo_alerts(lines, slo)
        lines.append("\n")


def _add_top_routes_section(lines: list[str]) -> None:
    """
    Ajoute la section des routes avec le plus d'erreurs 5xx.

    Args:
        lines: Lignes du rapport à modifier.
    """
    tops = _prom_top_routes_5xx(os.getenv("PROM_QUERY_URL"))
    lines.append("## Top routes 5xx (avg rate/5m)\n\n")
    if tops:
        lines.append("| Route | 5xx rate |\n|---|---:|\n")
        for route, val in tops:
            lines.append(f"| {route or '(unknown)'} | {val:.2f} |\n")
    else:
        lines.append("N/A (metrics unavailable)\n")
    lines.append("\n")


def generate_report(output_dir: Path, month: str | None = None) -> Path:
    """Generate the SLO report in `output_dir` and return the file path."""
    cfg = _load_slo_config(Path("slo.yaml"))
    y, m, label = _month_label(month)
    out_dir = output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"slo_report_{y}-{m:02d}.md"
    dash_base = os.getenv("GRAFANA_DASHBOARD_URL")

    lines: list[str] = []
    _add_slo_header(lines, cfg, label)
    _add_slo_objectives(lines, cfg, dash_base)
    _add_top_routes_section(lines)

    out.write_text("".join(lines), encoding="utf-8")
    return out


def export_json(
    output_path: Path, cfg: dict, breaches: list[dict[str, Any]], month: str | None
) -> Path:
    """Export a machine-readable SLO summary with breaches list."""
    y, m, _ = _month_label(month)
    freeze = any(b.get("id", "").startswith("policy_freeze_") for b in breaches)
    payload = {
        "service": cfg.get("service"),
        "version": cfg.get("version"),
        "owner": cfg.get("owner"),
        "month": f"{y}-{m:02d}",
        "slo_count": len(cfg.get("slos", [])),
        "breaches": breaches,
        "ok": len(breaches) == 0,
        "freeze": freeze,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    """
    Point d'entrée principal pour la génération de rapport SLO.

    Génère un rapport Markdown sur les Service Level Objectives à partir du fichier de configuration
    slo.yaml.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="artifacts/slo",
        help="Output directory for the Markdown report",
    )
    parser.add_argument("--json-out", default=None, help="Optional JSON export path")
    parser.add_argument(
        "--metrics",
        default=None,
        help="Optional synthetic metrics JSON for breach evaluation",
    )
    parser.add_argument(
        "--fail-on-breach", action="store_true", help="Exit 1 if any SLO is breached"
    )
    parser.add_argument("--month", default=None, help="YYYY-MM (default: current)")
    args = parser.parse_args()
    out_md = generate_report(Path(args.output_dir), args.month)
    cfg = _load_slo_config(Path("slo.yaml"))
    metrics = _load_metrics(Path(args.metrics)) if args.metrics else {}
    breaches = evaluate_breaches(cfg, metrics)
    if args.json_out:
        out_json = export_json(Path(args.json_out), cfg, breaches, args.month)
        print(str(out_json))
    print(str(out_md))
    if args.fail_on_breach and breaches:
        # Print simple summary before failing
        for b in breaches:
            print(f"BREACH: {b['id']}: {b['reason']}")
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
