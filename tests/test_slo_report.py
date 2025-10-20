from __future__ import annotations

import os
from pathlib import Path

from scripts.slo_report import generate_report


def test_slo_report_generation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GRAFANA_DASHBOARD_URL", "https://grafana.example.com/d/astro")
    out = generate_report(tmp_path)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # Should contain key sections and SLO names
    assert "SLO Report" in text
    assert "API availability" in text
    assert "Chat P95 latency" in text
    assert "Monthly LLM budget" in text
    # Dashboard link present
    assert "https://grafana.example.com" in text

