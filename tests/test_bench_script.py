# ============================================================
# Tests : tests/test_bench_script.py
# Objet  : Vérifier l'exécution du bench (squelette).
# ============================================================
"""
Tests pour les scripts de benchmark.

Ce module teste l'exécution des scripts de benchmark pour vérifier leur fonctionnement de base.
"""

from __future__ import annotations

import subprocess


def test_bench_runs_smoke():
    """Teste que le script de benchmark s'exécute sans erreur."""
    code = subprocess.call(
        [
            "python",
            "-m",
            "backend.scripts.bench_retrieval",
            "--adapter",
            "faiss",
            "--docs",
            "1000",
        ]
    )
    assert code == 0
