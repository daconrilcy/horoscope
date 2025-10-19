"""
Tâches Celery pour le rendu PDF.

Rend un PDF pour un thème natal existant identifié par `chart_id`, puis tente de
le mettre en cache dans Redis (si disponible) pendant 24h.
"""

from __future__ import annotations

from backend.app.celery_app import celery_app
from backend.core.container import container
from backend.domain.pdf_service import render_natal_pdf


@celery_app.task(name="backend.tasks.render_pdf")
def render_pdf_task(chart_id: str) -> str:
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
