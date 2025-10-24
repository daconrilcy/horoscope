#!/usr/bin/env python3
"""
Script de génération automatique de l'Evidence Pack v4.1
Génère les artefacts de release avec métadonnées et signatures
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Configuration
RELEASE_VERSION = "v4.1.0"
RELEASE_DATE = datetime.now(UTC).isoformat()
ARTIFACTS_DIR = Path("artifacts/release_v4_1")


def generate_file_hash(file_path: Path) -> str:
    """Génère le hash SHA-256 d'un fichier."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def collect_test_results() -> dict[str, Any]:
    """Collecte les résultats des tests de versioning."""
    try:
        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "tests/test_api_versioning.py",
                "--json-report",
                "--json-report-file=/tmp/pytest-report.json",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        # Lire le rapport JSON si disponible
        report_file = Path("/tmp/pytest-report.json")
        if report_file.exists():
            with open(report_file) as f:
                report = json.load(f)
                return {
                    "total": report.get("summary", {}).get("total", 0),
                    "passed": report.get("summary", {}).get("passed", 0),
                    "failed": report.get("summary", {}).get("failed", 0),
                    "exit_code": result.returncode,
                }
    except Exception as e:
        print(f"Warning: Could not collect test results: {e}")

    return {"total": 0, "passed": 0, "failed": 0, "exit_code": 1}


def collect_metrics_snapshot() -> dict[str, Any]:
    """Collecte un snapshot des métriques Prometheus."""
    return {
        "timestamp": RELEASE_DATE,
        "metrics": {
            "apigw_legacy_hits_total": "Counter for legacy route hits",
            "apigw_redirects_total": "Counter for redirect responses",
            "http_responses_total": "Counter for all HTTP responses",
        },
        "promql_queries": [
            "sum(rate(apigw_legacy_hits_total[1h])) by (route)",
            "sum(rate(apigw_redirects_total[1h])) by (route, status)",
            "sum(rate(http_responses_total[1h])) by (route)",
        ],
    }


def generate_artifacts_manifest() -> dict[str, Any]:
    """Génère le manifeste des artefacts."""
    manifest = {
        "release": {
            "version": RELEASE_VERSION,
            "date": RELEASE_DATE,
            "phase": "4.1",
            "issue": "#51",
            "title": "API versioning /v1 + deprecation policy",
        },
        "artifacts": {},
        "checksums": {},
        "test_results": collect_test_results(),
        "metrics": collect_metrics_snapshot(),
        "compliance": {
            "rfc_9745": "Deprecation HTTP Header",
            "rfc_8594": "Sunset HTTP Header",
            "rfc_8288": "Web Linking",
            "rfc_7231": "HTTP Semantics",
        },
    }

    # Collecter les fichiers d'artefacts
    artifacts_files = [
        "evidence_pack_v4_1.md",
        "versioning_deprecation_policy.md",
        "openapi_versioning.md",
        "legacy_traffic_decay.json",
    ]

    for file_name in artifacts_files:
        file_path = ARTIFACTS_DIR / file_name
        if file_path.exists():
            manifest["artifacts"][file_name] = {
                "path": str(file_path),
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC).isoformat(),
            }
            manifest["checksums"][file_name] = generate_file_hash(file_path)

    return manifest


def main() -> None:
    """Fonction principale."""
    print(f"🚀 Generating Evidence Pack {RELEASE_VERSION}")

    # Créer le répertoire des artefacts
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # Générer le manifeste
    manifest = generate_artifacts_manifest()

    # Sauvegarder le manifeste
    manifest_file = ARTIFACTS_DIR / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    # Générer le hash du manifeste
    manifest_hash = generate_file_hash(manifest_file)

    # Créer le fichier de signature
    signature_file = ARTIFACTS_DIR / "signature.txt"
    with open(signature_file, "w") as f:
        f.write(f"Evidence Pack {RELEASE_VERSION}\n")
        f.write(f"Generated: {RELEASE_DATE}\n")
        f.write(f"Manifest SHA-256: {manifest_hash}\n")
        f.write(f"Total artifacts: {len(manifest['artifacts'])}\n")
        f.write(
            f"Test results: {manifest['test_results']['passed']}/{manifest['test_results']['total']} passed\n"
        )

    print(f"✅ Evidence Pack generated in {ARTIFACTS_DIR}")
    print(f"📋 Manifest: {manifest_file}")
    print(f"🔐 Signature: {signature_file}")
    print(
        f"🧪 Tests: {manifest['test_results']['passed']}/{manifest['test_results']['total']} passed"
    )
    print(f"📊 Metrics: {len(manifest['metrics']['metrics'])} configured")


if __name__ == "__main__":
    main()
