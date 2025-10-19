from fastapi.testclient import TestClient

from backend.api import routes_chat
from backend.app.main import app
from backend.domain.chat_orchestrator import ChatOrchestrator
from backend.tests.fakes import FakeLLM


def run():
    routes_chat.orch = ChatOrchestrator(llm=FakeLLM())

    c = TestClient(app)

    # 1) signup plus user
    email = "plus@example.com"
    pwd = "pass1234"
    c.post(
        "/auth/signup",
        json={"email": email, "password": pwd, "entitlements": ["plus"]},
    )

    # 2) login
    login = c.post("/auth/login", json={"email": email, "password": pwd})
    token = login.json()["access_token"]

    # 3) create chart
    natal = c.post(
        "/horoscope/natal",
        json={
            "name": "T",
            "date": "1990-01-01",
            "time": None,
            "tz": "Europe/Paris",
            "lat": 48.85,
            "lon": 2.35,
            "time_certainty": "exact",
        },
    ).json()

    # 4) chat advise
    headers = {"Authorization": f"Bearer {token}"}
    r = c.post(
        "/chat/advise",
        json={"chart_id": natal["id"], "question": "Conseils pour aujourd'hui ?"},
        headers=headers,
    )
    print("status:", r.status_code)
    print("payload:", r.json())


if __name__ == "__main__":
    run()
