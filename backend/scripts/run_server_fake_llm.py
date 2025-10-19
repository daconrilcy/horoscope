import os

# Ensure local-friendly defaults BEFORE importing app/modules
os.environ.setdefault("EMBEDDINGS_PROVIDER", "local")
os.environ.setdefault("OPENAI_API_KEY", "test")

import uvicorn  # noqa: E402

from backend.api import routes_chat  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.domain.chat_orchestrator import ChatOrchestrator  # noqa: E402
from backend.tests.fakes import FakeLLM  # noqa: E402


def main():
    routes_chat.orch = ChatOrchestrator(llm=FakeLLM())

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
