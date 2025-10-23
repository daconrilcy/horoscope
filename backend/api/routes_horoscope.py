"""
Routes liées aux horoscopes: création de thème, lecture quotidienne et PDF.

Ce module regroupe les endpoints `/horoscope` pour créer un thème natal, récupérer les informations
du jour, et générer un PDF sommaire avec cache.
"""

import datetime as dt
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.api.routes_auth import get_current_user
from backend.api.schemas import BirthRequest, NatalResponse, TodayResponse
from backend.core.container import container
from backend.domain.entities import BirthInput, User
from backend.domain.entitlements import require_entitlement
from backend.domain.pdf_service import render_natal_pdf
from backend.domain.services import HoroscopeService

router = APIRouter(prefix="/horoscope", tags=["horoscope"])
service = HoroscopeService(
    container.astro, container.content_repo, container.chart_repo
)
current_user_dep = Depends(get_current_user)


@router.post("/natal", response_model=NatalResponse)
def create_natal(payload: BirthRequest):
    """
    Crée et enregistre un thème natal.

    Paramètres:
    - payload: `BirthRequest` contenant les informations de naissance.

    Retour:
    - `NatalResponse` (id, propriétaire, et données de carte).
    """
    chart = service.compute_natal(BirthInput(**payload.model_dump()))
    return chart


@router.get("/today/{chart_id}", response_model=TodayResponse)
def get_today(chart_id: str):
    """
    Retourne les informations quotidiennes pour un thème existant.

    Paramètres:
    - chart_id: identifiant du thème natal préalablement créé.

    Retour: `TodayResponse` avec leaders, influences, EAO et extraits.
    """
    try:
        data = service.get_today(chart_id, user=None)
        return data
    except KeyError as err:
        raise HTTPException(status_code=404, detail="Chart not found") from err


@router.get("/pdf/natal/{chart_id}", response_class=StreamingResponse)
def pdf_natal(chart_id: str):
    """Génère un PDF sommaire du thème natal avec cache Redis journalier."""
    chart = container.chart_repo.get(chart_id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")

    today = dt.date.today().isoformat()
    key = f"pdf:natal:{chart_id}:{today}"
    pdf_bytes: bytes | None = None

    # Try redis cache (reuse user_repo client if present)
    if getattr(container, "user_repo", None) and getattr(
        container.settings, "REDIS_URL", None
    ):
        try:
            raw = container.user_repo.client.get(key)
            if raw:
                pdf_bytes = (
                    raw
                    if isinstance(raw, bytes | bytearray)
                    else str(raw).encode("latin-1")
                )
        except Exception:
            pass

    if not pdf_bytes:
        pdf_bytes = render_natal_pdf(chart)
        try:
            if getattr(container.settings, "REDIS_URL", None):
                container.user_repo.client.setex(key, 86400, pdf_bytes)  # 24h
        except Exception:
            pass

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=natal_{chart_id}.pdf"},
    )


@router.get("/today/premium/{chart_id}")
def get_today_premium(chart_id: str, user: User = current_user_dep):
    """Endpoint premium: nécessite l'entitlement "plus".

    Retourne les mêmes données que `/today/{chart_id}` avec un indicateur `premium: true`.
    """
    require_entitlement(user, "plus")
    try:
        data = service.get_today(chart_id, user=user)
        data.update({"premium": True})
        return data
    except KeyError as err:
        raise HTTPException(status_code=404, detail="Chart not found") from err
