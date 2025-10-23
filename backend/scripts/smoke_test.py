"""
Quick smoke test for API endpoints using TestClient.

Checks:
- GET /health
- POST /horoscope/natal
- GET /horoscope/today/{id}
- GET /horoscope/pdf/natal/{id}
"""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.container import container
from backend.infra.astro.fake_deterministic import FakeDeterministicAstro


def main() -> None:
    """
    Point d'entrée principal pour les tests de fumée.

    Exécute une série de tests de base pour vérifier que l'application fonctionne correctement avec
    un moteur déterministe.
    """
    # Use deterministic engine for repeatable output
    container.astro = FakeDeterministicAstro()
    client = TestClient(app)

    # Health
    r = client.get("/health")
    print("/health:", r.status_code, r.json())

    # Create natal
    birth = {
        "name": "Smoke Test",
        "date": "1990-01-01",
        "time": None,
        "tz": "Europe/Paris",
        "lat": 48.8566,
        "lon": 2.3522,
        "time_certainty": "morning",
    }
    r = client.post("/horoscope/natal", json=birth)
    print("/horoscope/natal:", r.status_code)
    chart_id = r.json()["id"]

    # Today
    r = client.get(f"/horoscope/today/{chart_id}")
    data = r.json()
    print(
        "/horoscope/today:",
        r.status_code,
        {
            "date": data.get("date"),
            "leaders": len(data.get("leaders", [])),
            "eao": data.get("eao"),
            "precision": data.get("precision_score"),
        },
    )

    # PDF
    r = client.get(f"/horoscope/pdf/natal/{chart_id}")
    print(
        "/horoscope/pdf/natal:",
        r.status_code,
        r.headers.get("content-type"),
        len(r.content),
    )

    print("Smoke test OK")


if __name__ == "__main__":
    main()
