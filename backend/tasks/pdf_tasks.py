"""
Tâches Celery pour le rendu PDF.

Rend un PDF pour un thème natal existant identifié par `chart_id`, puis tente de
le mettre en cache dans Redis (si disponible) pendant 24h.
"""

from __future__ import annotations

from backend.app.celery_app import celery_app
from backend.core.container import container
from backend.domain.pdf_service import render_natal_pdf
from backend.infra.ops.idempotency import idempotency_store, make_idem_key


@celery_app.task(name="backend.tasks.render_pdf")
def render_pdf_task(chart_id: str) -> str:
    # Idempotency: avoid duplicate work within TTL window
    idem_key = make_idem_key("render_pdf", chart_id)
    if not idempotency_store.acquire(idem_key, ttl=300):
        return "duplicate"
    chart = container.chart_repo.get(chart_id)
    if not chart:
        return "not_found"
    pdf_bytes = render_natal_pdf(chart)
    key = f"pdf:natal:{chart_id}"
    try:
        if getattr(container.settings, "REDIS_URL", None):
            container.user_repo.client.setex(key, 86400, pdf_bytes)
    except Exception:
        # best-effort cache
        pass
    return "ok"
