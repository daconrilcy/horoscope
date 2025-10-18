"""Routes liées au calcul et à la consultation des cartes (charts).

Objectif du module
------------------
- Offrir des endpoints REST pour calculer une carte à partir de données de
  naissance, puis la retrouver par son identifiant.
"""

from api.deps import chart_repo, chart_service
from api.schemas import ChartResponse, ComputeChartRequest
from domain.models import BirthData
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/charts", tags=["charts"])


@router.post("/compute", response_model=ChartResponse)
def compute_chart(payload: ComputeChartRequest):
    """Calcule et persiste une carte à partir des données fournies."""
    chart = chart_service.compute_chart(BirthData(**payload.model_dump()))
    chart_repo.save(chart)
    return chart


@router.get("/{chart_id}", response_model=ChartResponse)
def get_chart(chart_id: str):
    """Récupère une carte existante par identifiant, sinon 404."""
    chart = chart_repo.get(chart_id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    return chart
