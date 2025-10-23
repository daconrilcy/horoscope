"""
Tests pour la détection de violations SLO.

Ce module teste l'évaluation des violations SLO basée sur les métriques de performance et les
politiques de gel en cas de taux de burn élevés.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.slo_report import _load_slo_config, evaluate_breaches, export_json


def _write_metrics(tmp_path: Path, p95: float, p99: float, err: float) -> Path:
    m = {"endpoints": {"GET /chat/answer": {"p95": p95, "p99": p99, "error_rate": err}}}
    f = tmp_path / "metrics.json"
    f.write_text(json.dumps(m), encoding="utf-8")
    return f


def test_no_breach_when_under_targets(tmp_path: Path) -> None:
    """
    Teste qu'aucune violation SLO n'est détectée quand les métriques sont sous les seuils.

    Vérifie que lorsque les métriques de performance sont dans les limites acceptables, aucune
    violation SLO n'est signalée.
    """
    cfg = _load_slo_config(Path("slo.yaml"))
    metrics_path = _write_metrics(tmp_path, p95=0.28, p99=0.65, err=0.003)
    breaches = evaluate_breaches(
        cfg, json.loads(metrics_path.read_text(encoding="utf-8"))
    )
    assert breaches == []
    out = export_json(tmp_path / "report.json", cfg, breaches, month="2025-10")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["slo_count"] >= 1


def test_breach_detected_when_over_targets(tmp_path: Path) -> None:
    """
    Teste la détection de violations SLO quand les métriques dépassent les seuils.

    Vérifie que les violations SLO sont correctement détectées et signalées quand les métriques de
    performance dépassent les limites configurées.
    """
    cfg = _load_slo_config(Path("slo.yaml"))
    metrics_path = _write_metrics(tmp_path, p95=0.40, p99=0.80, err=0.010)
    breaches = evaluate_breaches(
        cfg, json.loads(metrics_path.read_text(encoding="utf-8"))
    )
    assert any(b["id"].startswith("endpoint_chat_answer_") for b in breaches)
    out = export_json(tmp_path / "report.json", cfg, breaches, month="2025-10")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert len(payload["breaches"]) >= 1


def test_low_traffic_gates_breaches(tmp_path: Path) -> None:
    """
    Teste que les violations SLO sont ignorées en cas de faible trafic.

    Vérifie que même si les métriques dépassent les seuils, aucune violation n'est signalée quand le
    trafic est trop faible (protection contre les faux positifs).
    """
    cfg = _load_slo_config(Path("slo.yaml"))
    # Over targets but low traffic → should be ignored
    metrics = {
        "endpoints": {
            "GET /chat/answer": {
                "p95": 0.40,
                "p99": 0.80,
                "error_rate": 0.010,
                "requests_5m": 10,
            }
        }
    }
    breaches = evaluate_breaches(cfg, metrics)
    assert breaches == []


def test_freeze_policy_when_burn_rates_high(tmp_path: Path) -> None:
    """
    Teste l'activation de la politique de gel quand les taux de burn sont élevés.

    Vérifie que la politique de gel est déclenchée quand les taux de burn sur 1h et 6h dépassent les
    seuils configurés.
    """
    cfg = _load_slo_config(Path("slo.yaml"))
    metrics = {
        "endpoints": {
            "GET /chat/answer": {
                "p95": 0.20,
                "p99": 0.40,
                "error_rate": 0.002,
                "requests_5m": 1000,
                "burn_rate_1h": 2.5,
                "burn_rate_6h": 1.2,
            }
        }
    }
    breaches = evaluate_breaches(cfg, metrics)
    assert any(b["id"].startswith("policy_freeze_") for b in breaches)
