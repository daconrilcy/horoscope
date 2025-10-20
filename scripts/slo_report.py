from __future__ import annotations

"""Generate a monthly SLO report in Markdown from slo.yaml.

Usage:
  python -m scripts.slo_report --output-dir artifacts/slo --month 2025-10

Notes:
- slo.yaml is JSON-compatible YAML to avoid extra dependencies.
- Dashboard base URL can be provided via GRAFANA_DASHBOARD_URL.
"""

import argparse
import calendar
import json
import os
from datetime import date
from pathlib import Path


def _load_slo_config(path: Path) -> dict:
    """Load SLO configuration (JSON-compatible YAML)."""
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def _month_label(ym: str | None) -> tuple[int, int, str]:
    """Return (year, month, label) for the given YYYY-MM or current month."""
    if ym and len(ym) == 7 and ym[4] == "-":
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


def generate_report(output_dir: Path, month: str | None = None) -> Path:
    """Generate the SLO report in `output_dir` and return the file path."""
    cfg = _load_slo_config(Path("slo.yaml"))
    y, m, label = _month_label(month)
    out_dir = output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"slo_report_{y}-{m:02d}.md"
    dash_base = os.getenv("GRAFANA_DASHBOARD_URL")

    lines: list[str] = []
    lines.append(f"# SLO Report — {cfg.get('service','service')} — {label}\n\n")
    lines.append("## Summary\n\n")
    lines.append("- Version: " + str(cfg.get("version", 1)) + "\n")
    lines.append("- Owner: " + str(cfg.get("owner", "unknown")) + "\n\n")
    lines.append("## Objectives\n\n")
    for slo in cfg.get("slos", []):
        name = slo.get("name") or slo.get("id")
        lines.append(f"### {name}\n\n")
        lines.append("- Objective: " + str(slo.get("objective", "")) + "\n")
        if "target" in slo:
            lines.append(f"- Target: {slo['target']}\n")
        if "target_seconds" in slo:
            lines.append(f"- Target seconds: {slo['target_seconds']}\n")
        if "rto_minutes" in slo:
            lines.append(f"- RTO minutes: {slo['rto_minutes']}\n")
        if "rpo_minutes" in slo:
            lines.append(f"- RPO minutes: {slo['rpo_minutes']}\n")
        if "target_usd" in slo:
            lines.append(f"- Target budget (USD): {slo['target_usd']}\n")
        lines.append(f"- Window: {slo.get('window','30d')}\n")
        lines.append(f"- Dashboard: {_dashboard_link(dash_base, slo.get('id',''))}\n")
        alerts = slo.get("alerts", [])
        if alerts:
            lines.append("- Alerts:\n")
            for a in alerts:
                lines.append(f"  - {a.get('name')}: {a.get('expr')} (sev={a.get('severity')})\n")
        lines.append("\n")
    out.write_text("".join(lines), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/slo", help="Output directory for the report")
    parser.add_argument("--month", default=None, help="YYYY-MM (default: current)")
    args = parser.parse_args()
    p = generate_report(Path(args.output_dir), args.month)
    print(str(p))


if __name__ == "__main__":  # pragma: no cover
    main()

