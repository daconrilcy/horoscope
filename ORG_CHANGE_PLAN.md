
# Org Change Plan — Horoscope Backend (FastAPI) — Hand-off for VSCode GPT Agent

## 🎯 Objective
Refactor the backend structure to:
- Internalize the **astro engine** (no external API calls).
- Introduce **uncertainty scoring** (`time_certainty` → `precision_score`).
- Add an initial **Today heuristic** (leaders/influences + Energy/Attention/Opportunity).
- Add a **ContentRepository** (JSON for now).
- Provide a **minimal PDF** route for natal chart.
- Use **Redis** repository with in-memory fallback.
- Keep architecture DDD/Clean: `api/`, `app/`, `core/`, `domain/`, `infra/`, `middlewares/`, `tests/`, `docker/`.

This plan assumes the repo root contains the v1 scaffold and will transform it to the v2 layout described below.

---

## ✅ Deliverables
1) Updated project tree (see **Target Structure**).  
2) Code changes implemented exactly as described (diffs below).  
3) All tests green via `pytest`.  
4) Docker stack up with `redis` service.  
5) Endpoints operational:
   - `GET /health`
   - `POST /horoscope/natal`
   - `GET /horoscope/today/{chart_id}`
   - `GET /horoscope/pdf/natal/{chart_id}`

---

## 📦 Target Structure
```
api/
  schemas.py
  routes_health.py
  routes_horoscope.py
app/
  main.py
core/
  container.py
  logging.py
  settings.py
domain/
  entities.py
  services.py
  today_heuristic.py
  uncertainty.py
infra/
  astro/
    internal_astro.py
  content.json
  content_repo.py
  repositories.py
middlewares/
  request_id.py
  timing.py
docker/
  Dockerfile
  docker-compose.yml
tests/
  test_health.py
  test_today_flow.py
.env.example
pyproject.toml
requirements.txt
README.md
```

---

## 🧩 High-level Changes
- Replace any **external astrology client** with `infra/astro/internal_astro.py`.
- Replace the **chart repo** with `RedisChartRepo` (fallback to `InMemoryChartRepo` when `REDIS_URL` is not set or Redis is unavailable).
- Extend domain with **uncertainty** and **today heuristic**.
- Add **content** JSON + repository; wire into `HoroscopeService`.
- Add **PDF** generation route using ReportLab.

---

## 🛠 Steps — Do in This Order

### 0) Dependencies
Edit `requirements.txt` (append if not present):
```
redis>=5.0.8
reportlab>=4.2.5
```
Ensure `pyproject.toml` contains same deps (keep FastAPI/Pydantic versions).

### 1) Core Wiring
Create/replace `core/container.py` with:
```python
from core.settings import get_settings
from infra.repositories import InMemoryChartRepo, RedisChartRepo
from infra.content_repo import JSONContentRepository
from infra.astro.internal_astro import InternalAstroEngine
import os

class Container:
    def __init__(self):
        self.settings = get_settings()
        self.content_repo = JSONContentRepository(path=os.path.join(os.path.dirname(__file__), "..", "infra", "content.json"))
        self.astro = InternalAstroEngine()
        if self.settings.REDIS_URL:
            try:
                self.chart_repo = RedisChartRepo(self.settings.REDIS_URL)
            except Exception:
                self.chart_repo = InMemoryChartRepo()
        else:
            self.chart_repo = InMemoryChartRepo()

container = Container()
```

### 2) Domain — Entities & Uncertainty
Create `domain/entities.py`:
```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

TimeCertainty = Literal["exact", "morning", "afternoon", "evening", "unknown"]

class User(BaseModel):
    id: str
    email: str
    entitlements: list[str] = Field(default_factory=list)

class BirthInput(BaseModel):
    name: str
    date: str           # YYYY-MM-DD
    time: Optional[str] # HH:MM or None
    tz: str             # IANA TZ
    lat: float
    lon: float
    time_certainty: TimeCertainty = "exact"
```

Create `domain/uncertainty.py`:
```python
from domain.entities import TimeCertainty

def precision_score(time_certainty: TimeCertainty) -> int:
    mapping = {
        "exact": 5,
        "morning": 3,
        "afternoon": 3,
        "evening": 3,
        "unknown": 1,
    }
    return mapping.get(time_certainty, 1)
```

### 3) Domain — Today Heuristic
Create `domain/today_heuristic.py`:
```python
from typing import Any, Dict, List, Tuple

def score_factor(f: Dict[str, Any]) -> float:
    return f.get("weight", 1.0) * f.get("intensity", 1.0) - f.get("friction", 0.0)

def pick_today(transits: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ranked = sorted(transits, key=score_factor, reverse=True)
    leaders = ranked[:3]
    influences = ranked[3:6]
    return leaders, influences

def energy_attention_opportunity(leaders: List[Dict[str, Any]]) -> Dict[str, int]:
    e = sum(1 for f in leaders if f.get("axis") in ("SUN","MARS","ASC"))
    a = sum(1 for f in leaders if f.get("axis") in ("MERCURY","SATURN","MC"))
    o = sum(1 for f in leaders if f.get("axis") in ("VENUS","JUPITER","NN"))
    return {"energy": e, "attention": a, "opportunity": o}
```

### 4) Domain — Service
Create/replace `domain/services.py`:
```python
import uuid
from datetime import date as _date
from typing import Any, Dict
from domain.entities import BirthInput, User
from domain.today_heuristic import pick_today, energy_attention_opportunity

class HoroscopeService:
    def __init__(self, astro_engine, content_repo, chart_repo):
        self.astro = astro_engine
        self.content = content_repo
        self.charts = chart_repo

    def compute_natal(self, birth: BirthInput) -> Dict[str, Any]:
        chart = self.astro.compute_natal_chart(birth)
        chart_id = str(uuid.uuid4())
        chart_record = {"id": chart_id, "owner": birth.name, "chart": chart}
        self.charts.save(chart_record)
        return chart_record

    def get_today(self, chart_id: str, user: User | None = None) -> Dict[str, Any]:
        chart = self.charts.get(chart_id)
        if not chart:
            raise KeyError("chart_not_found")
        today = _date.today().isoformat()
        transits = self.astro.compute_daily_transits(chart["chart"], today)
        leaders, influences = pick_today(transits)
        eao = energy_attention_opportunity(leaders)
        snippets = [self.content.get_snippet(f["snippet_id"]) for f in leaders if "snippet_id" in f]
        return {
            "date": today,
            "leaders": leaders,
            "influences": influences,
            "eao": eao,
            "snippets": snippets,
            "precision_score": chart["chart"].get("precision_score", 1),
        }
```

### 5) Infra — Astro Engine (Internal)
Create `infra/astro/internal_astro.py`:
```python
from domain.entities import BirthInput
from domain.uncertainty import precision_score
from typing import Dict, Any, List
import random

class InternalAstroEngine:
    def compute_natal_chart(self, birth: BirthInput) -> Dict[str, Any]:
        return {
            "name": birth.name,
            "birth": birth.model_dump(),
            "precision_score": precision_score(birth.time_certainty),
            "factors": [{"axis": "SUN"}, {"axis": "ASC"}, {"axis": "MC"}],
        }

    def compute_daily_transits(self, natal: Dict[str, Any], day_iso: str) -> List[Dict[str, Any]]:
        axes = ["SUN","MARS","ASC","MERCURY","SATURN","MC","VENUS","JUPITER","NN"]
        transits = []
        for i in range(6):
            axis = random.choice(axes)
            intensity = round(random.uniform(0.5, 1.5), 2)
            friction = round(random.uniform(0.0, 0.6), 2)
            weight = 1.0
            snippet_id = f"TODAY_{axis}_EN"
            transits.append({"axis": axis, "intensity": intensity, "friction": friction, "weight": weight, "snippet_id": snippet_id})
        return transits
```

### 6) Infra — Repositories
Create/replace `infra/repositories.py`:
```python
from typing import Dict, Any, Optional
import json, redis

class InMemoryChartRepo:
    def __init__(self):
        self._db: Dict[str, Dict[str, Any]] = {}

    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        self._db[record["id"]] = record
        return record

    def get(self, chart_id: str) -> Optional[Dict[str, Any]]:
        return self._db.get(chart_id)

class RedisChartRepo:
    def __init__(self, url: str):
        self.client = redis.Redis.from_url(url, decode_responses=True)

    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        key = f"chart:{record['id']}"
        self.client.set(key, json.dumps(record))
        return record

    def get(self, chart_id: str) -> Optional[Dict[str, Any]]:
        key = f"chart:{chart_id}"
        raw = self.client.get(key)
        return json.loads(raw) if raw else None
```

### 7) Infra — Content Repository
Create `infra/content_repo.py`:
```python
import json, os
from typing import Dict

class JSONContentRepository:
    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def get_snippet(self, snippet_id: str) -> Dict:
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(snippet_id, {"id": snippet_id, "text": "(content missing)"})
```

Seed `infra/content.json` with (create file):
```json
{
  "TODAY_SUN_EN": {"id": "TODAY_SUN_EN", "text": "Vitality is highlighted. Lean into confidence and visibility."},
  "TODAY_MARS_EN": {"id": "TODAY_MARS_EN", "text": "Action and drive surge. Channel it constructively."},
  "TODAY_ASC_EN": {"id": "TODAY_ASC_EN", "text": "First impressions matter today. Present your best self."},
  "TODAY_MERCURY_EN": {"id": "TODAY_MERCURY_EN", "text": "Focus on clear communication and learning."},
  "TODAY_SATURN_EN": {"id": "TODAY_SATURN_EN", "text": "Discipline pays. Respect limits and structure."},
  "TODAY_MC_EN": {"id": "TODAY_MC_EN", "text": "Career visibility increases. Align actions with goals."},
  "TODAY_VENUS_EN": {"id": "TODAY_VENUS_EN", "text": "Harmony, aesthetics, and relationships get a boost."},
  "TODAY_JUPITER_EN": {"id": "TODAY_JUPITER_EN", "text": "Growth and optimism. Think bigger, but stay grounded."},
  "TODAY_NN_EN": {"id": "TODAY_NN_EN", "text": "Destiny nudges you forward. Follow meaningful opportunities."}
}
```

### 8) API Schemas & Routes
Replace `api/schemas.py` with:
```python
from pydantic import BaseModel
from typing import Optional, Literal

class BirthRequest(BaseModel):
    name: str
    date: str
    time: Optional[str] = None
    tz: str
    lat: float
    lon: float
    time_certainty: Literal["exact","morning","afternoon","evening","unknown"] = "exact"

class NatalResponse(BaseModel):
    id: str
    owner: str
    chart: dict

class TodayResponse(BaseModel):
    date: str
    leaders: list[dict]
    influences: list[dict]
    eao: dict
    snippets: list[dict]
    precision_score: int
```

Create `api/routes_horoscope.py`:
```python
from fastapi import APIRouter, HTTPException
from api.schemas import BirthRequest, NatalResponse, TodayResponse
from domain.entities import BirthInput, User
from core.container import container
from domain.services import HoroscopeService
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.pagesizes import A4
import io
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/horoscope", tags=["horoscope"])
service = HoroscopeService(container.astro, container.content_repo, container.chart_repo)

@router.post("/natal", response_model=NatalResponse)
def create_natal(payload: BirthRequest):
    chart = service.compute_natal(BirthInput(**payload.model_dump()))
    return chart

@router.get("/today/{chart_id}", response_model=TodayResponse)
def get_today(chart_id: str):
    try:
        data = service.get_today(chart_id, user=None)
        return data
    except KeyError:
        raise HTTPException(status_code=404, detail="Chart not found")

@router.get("/pdf/natal/{chart_id}", response_class=StreamingResponse)
def pdf_natal(chart_id: str):
    chart = container.chart_repo.get(chart_id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    buffer = io.BytesIO()
    c = pdfcanvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    c.setTitle("Horoscope Natal Chart")
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height-80, "Natal Chart Summary")
    c.setFont("Helvetica", 12)
    c.drawString(50, height-110, f"Owner: {chart['owner']}")
    c.drawString(50, height-130, f"Precision Score: {chart['chart'].get('precision_score', 1)}")
    factors = ", ".join(f.get('axis','?') for f in chart['chart'].get('factors', []))
    c.drawString(50, height-150, f"Factors: {factors}")
    c.showPage()
    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename=natal_{chart_id}.pdf"})
```

Ensure `app/main.py` includes the new router:
```python
from fastapi import FastAPI
from core.logging import setup_logging
from core.container import container
from middlewares.request_id import RequestIDMiddleware
from middlewares.timing import TimingMiddleware
from api.routes_health import router as health_router
from api.routes_horoscope import router as horoscope_router

def create_app() -> FastAPI:
    setup_logging()
    settings = container.settings
    app = FastAPI(title=settings.APP_NAME, debug=settings.APP_DEBUG)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TimingMiddleware)
    app.include_router(health_router)
    app.include_router(horoscope_router)
    return app

app = create_app()
```

### 9) Docker — Add Redis
Replace `docker/docker-compose.yml` with:
```yaml
services:
  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - ../.env.example
    environment:
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ..:/app:cached
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

And ensure `docker/Dockerfile` has ReportLab fonts installed (example already OK with `fonts-dejavu-core`).

### 10) Tests
Add `tests/test_today_flow.py`:
```python
from fastapi.testclient import TestClient
from app.main import app

def test_natal_to_today_and_pdf():
    client = TestClient(app)
    birth = {
        "name": "Test User",
        "date": "1990-01-01",
        "time": None,
        "tz": "Europe/Paris",
        "lat": 48.8566,
        "lon": 2.3522,
        "time_certainty": "morning"
    }
    r = client.post("/horoscope/natal", json=birth)
    assert r.status_code == 200
    chart_id = r.json()["id"]

    r2 = client.get(f"/horoscope/today/{chart_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert "leaders" in data and len(data["leaders"]) > 0
    assert 1 <= data["precision_score"] <= 5

    r3 = client.get(f"/horoscope/pdf/natal/{chart_id}")
    assert r3.status_code == 200
    assert r3.headers["content-type"].startswith("application/pdf")
```

Keep/ensure `tests/test_health.py` exists.

---

## 🧪 Validation Commands
```bash
# Local
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q

# Run app
uvicorn app.main:app --reload --port 8000

# Docker
docker compose -f docker/docker-compose.yml up --build
```

### Quick Manual Checks
- `GET http://localhost:8000/health` → `{"status":"ok"}`
- `POST http://localhost:8000/horoscope/natal` with JSON body (name/date/tz/lat/lon/time_certainty) → returns `{id, owner, chart}`
- `GET http://localhost:8000/horoscope/today/{id}` → returns leaders/influences/E-A-O/snippets/precision_score
- `GET http://localhost:8000/horoscope/pdf/natal/{id}` → returns a PDF

---

## 🔒 Future Work Hooks (not in this change)
- Replace internal stub with **Skyfield/Swiss Ephemeris** using same interfaces.
- Extend `today_heuristic` with full priority/tie-breaker logic.
- SQL-backed `ContentRepository` + locales, tags, variants.
- AuthN/AuthZ (Keycloak/OAuth2) + Entitlements middleware.
- PDF caching (Redis) and P95 target < 1.5s.

---

## 📝 Commit Messages (suggested)
- `feat(astro): internalize astro engine and uncertainty scoring`
- `feat(today): add today heuristic skeleton with E/A/O`
- `feat(content): JSON content repo + seed snippets`
- `feat(pdf): natal chart PDF generation`
- `feat(repo): RedisChartRepo with in-memory fallback`
- `chore(docker): add redis service & env wiring`
- `test(flow): natal→today→pdf smoke test`

---

## 🤖 Prompts to Use in VSCode Agent (if needed)
- “Apply the Org Change Plan in `ORG_CHANGE_PLAN.md` exactly as written. Create missing files and update existing ones.”
- “Run pytest and fix any local import path issues by adjusting relative imports without changing module names.”
- “Ensure the Docker services start and `/health` returns 200.”

