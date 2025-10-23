"""
Module: celery_metrics_server.

But: Exposer les métriques Prometheus du worker Celery via un petit serveur WSGI.

Usage:
    python -m backend.infra.monitoring.celery_metrics_server --port 9109

    Notes:
    - Aucun secret n'est loggé.
    - Compatible Windows (wsgiref.simple_server).
    - Sécurité: par défaut, l'allowlist IP inclut 127.0.0.1 et ::1. En prod,
      placez ce service derrière un reverse-proxy (BasicAuth ou mTLS) ou
      étendez l'allowlist selon vos besoins.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any
from wsgiref.simple_server import make_server

from backend.infra.monitoring.celery_exporter import metrics_wsgi_app


def _parse_allowlist(allowlist: str) -> set[str]:
    return {ip.strip() for ip in (allowlist or "").split(",") if ip.strip()}


def build_metrics_app(allowlist: str) -> Callable[[dict[str, Any], Callable], Any]:
    """
    Construit une appli WSGI filtrant par IP avant d'exposer /metrics.

    - allowlist: liste d'IP séparées par des virgules (ex: "127.0.0.1,::1").
    """
    allowed = _parse_allowlist(allowlist)

    def _app(environ, start_response):  # type: ignore[no-untyped-def]
        # Détecter l'IP cliente (REMOTE_ADDR direct, sinon premier X-Forwarded-For)
        client = environ.get("REMOTE_ADDR") or ""
        xff = environ.get("HTTP_X_FORWARDED_FOR") or ""
        if xff:
            client = xff.split(",")[0].strip()
        if allowed and client not in allowed:
            start_response("403 FORBIDDEN", [("Content-Type", "text/plain")])
            return [b"forbidden"]
        return metrics_wsgi_app(environ, start_response)

    return _app


def main() -> None:
    """
    Point d'entrée CLI.

    Démarre un serveur WSGI minimal pour exposer /metrics.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="Adresse d'écoute")
    parser.add_argument("--port", default=9109, type=int, help="Port d'écoute")
    parser.add_argument(
        "--allowlist",
        default="127.0.0.1,::1",
        help="IPs autorisées (séparées par des virgules). Par défaut: 127.0.0.1,::1",
    )
    args = parser.parse_args()

    # `metrics_wsgi_app` est une application WSGI (callable environ/start_response)
    app = build_metrics_app(args.allowlist)
    with make_server(args.host, args.port, app) as httpd:
        print(f"[metrics] Listening on http://{args.host}:{args.port}/metrics")
        httpd.serve_forever()


if __name__ == "__main__":  # pragma: no cover - script entry
    main()
