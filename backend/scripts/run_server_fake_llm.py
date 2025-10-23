"""
Script de serveur de développement avec LLM factice.

Ce script lance un serveur de développement avec un LLM factice pour les tests et le développement
local sans dépendances externes.
"""

import os

# Ensure local-friendly defaults BEFORE importing app/modules
os.environ.setdefault("EMBEDDINGS_PROVIDER", "local")
os.environ.setdefault("OPENAI_API_KEY", "test")

import uvicorn

from backend.api import routes_chat
from backend.app.main import app
from backend.domain.chat_orchestrator import ChatOrchestrator
from backend.tests.fakes import FakeLLM


def main():
    """
    Point d'entrée principal pour le serveur avec LLM factice.

    Lance l'application FastAPI avec un LLM simulé pour faciliter le développement et les tests.
    """
    routes_chat.orch = ChatOrchestrator(llm=FakeLLM())

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
