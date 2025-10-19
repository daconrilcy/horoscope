# ============================================================
# Tests : tests/test_bench_script.py
# Objet  : Vérifier l'exécution du bench (squelette).
# ============================================================

from __future__ import annotations

import subprocess


def test_bench_runs_smoke():
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
