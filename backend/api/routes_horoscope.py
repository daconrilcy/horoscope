import io

from core.container import container
from domain.entities import BirthInput
from domain.services import HoroscopeService
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdfcanvas

from api.schemas import BirthRequest, NatalResponse, TodayResponse

router = APIRouter(prefix="/horoscope", tags=["horoscope"])
service = HoroscopeService(container.astro, container.content_repo, container.chart_repo)


@router.post("/natal", response_model=NatalResponse)
def create_natal(payload: BirthRequest):
    """Calcule et enregistre un thème natal à partir d'une requête.

    Paramètres:
    - payload: `BirthRequest` contenant les informations de naissance.

    Retour: `NatalResponse` (id, propriétaire, et données de carte).
    """
    chart = service.compute_natal(BirthInput(**payload.model_dump()))
    return chart


@router.get("/today/{chart_id}", response_model=TodayResponse)
def get_today(chart_id: str):
    """Retourne les informations quotidiennes pour un thème existant.

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
    """Génère un PDF sommaire du thème natal.

    Paramètres:
    - chart_id: identifiant du thème natal.

    Retour: `StreamingResponse` PDF inline (application/pdf).
    """
    chart = container.chart_repo.get(chart_id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    buffer = io.BytesIO()
    c = pdfcanvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    c.setTitle("Horoscope Natal Chart")
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 80, "Natal Chart Summary")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 110, f"Owner: {chart['owner']}")
    c.drawString(50, height - 130, f"Precision Score: {chart['chart'].get('precision_score', 1)}")
    factors = ", ".join(f.get('axis', '?') for f in chart['chart'].get('factors', []))
    c.drawString(50, height - 150, f"Factors: {factors}")
    c.showPage()
    c.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=natal_{chart_id}.pdf"},
    )
