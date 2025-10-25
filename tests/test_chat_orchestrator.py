"""Tests pour l'orchestrateur de chat astrologique.

Ce module teste l'orchestrateur qui coordonne la récupération de documents et la génération de
réponses.
"""

from __future__ import annotations

from unittest.mock import Mock

from backend.domain.chat_orchestrator import ChatOrchestrator, _ctx
from backend.domain.retrieval_types import Document, ScoredDocument

# Constantes pour éviter les erreurs PLR2004 (Magic values)
EXPECTED_LINES_COUNT = 6
EXPECTED_MESSAGES_COUNT = 2
DEFAULT_K_VALUE = 6


def test_ctx_function_basic() -> None:
    """Teste la fonction _ctx avec des documents de base."""
    scored_docs = [
        ScoredDocument(doc=Document(id="doc1", text="Premier document"), score=0.9),
        ScoredDocument(doc=Document(id="doc2", text="Deuxième document"), score=0.8),
        ScoredDocument(doc=Document(id="doc3", text="Troisième document"), score=0.7),
    ]

    result = _ctx(scored_docs)

    expected = "- Premier document\n- Deuxième document\n- Troisième document"
    assert result == expected


def test_ctx_function_empty() -> None:
    """Teste la fonction _ctx avec une liste vide."""
    scored_docs = []

    result = _ctx(scored_docs)

    assert result == ""


def test_ctx_function_more_than_six() -> None:
    """Teste la fonction _ctx avec plus de 6 documents."""
    scored_docs = [
        ScoredDocument(doc=Document(id=f"doc{i}", text=f"Document {i}"), score=0.9 - i * 0.1)
        for i in range(8)
    ]

    result = _ctx(scored_docs)

    # Vérifier que seuls les 6 premiers sont utilisés
    lines = result.split("\n")
    assert len(lines) == EXPECTED_LINES_COUNT
    assert "- Document 0" in result
    assert "- Document 5" in result
    assert "- Document 6" not in result
    assert "- Document 7" not in result


def test_chat_orchestrator_init_default() -> None:
    """Teste l'initialisation de l'orchestrateur avec les valeurs par défaut."""
    orchestrator = ChatOrchestrator()

    assert orchestrator.retriever is not None
    assert orchestrator.llm is not None


def test_chat_orchestrator_init_custom() -> None:
    """Teste l'initialisation de l'orchestrateur avec des composants personnalisés."""
    mock_retriever = Mock()
    mock_llm = Mock()

    orchestrator = ChatOrchestrator(retriever=mock_retriever, llm=mock_llm)

    assert orchestrator.retriever == mock_retriever
    assert orchestrator.llm == mock_llm


def test_chat_orchestrator_init_partial() -> None:
    """Teste l'initialisation de l'orchestrateur avec un seul composant personnalisé."""
    mock_retriever = Mock()

    orchestrator = ChatOrchestrator(retriever=mock_retriever)

    assert orchestrator.retriever == mock_retriever
    assert orchestrator.llm is not None  # Utilise la valeur par défaut


def test_advise_basic() -> None:
    """Teste la génération de conseils de base."""
    mock_retriever = Mock()
    mock_llm = Mock()

    # Mock des données
    chart = {"chart": {"precision_score": 5}}
    today = {"eao": {"energy": 2, "attention": 1, "opportunity": 3}}
    question = "Comment optimiser ma journée ?"

    scored_docs = [ScoredDocument(doc=Document(id="doc1", text="Document astrologique"), score=0.9)]

    mock_retriever.query.return_value = scored_docs
    mock_llm.generate.return_value = "Voici mes conseils astrologiques"

    orchestrator = ChatOrchestrator(retriever=mock_retriever, llm=mock_llm)

    result_text, result_usage = orchestrator.advise(chart, today, question)

    # Vérifications
    assert result_text == "Voici mes conseils astrologiques"
    assert result_usage is None

    # Vérifier que les méthodes ont été appelées
    mock_retriever.query.assert_called_once()
    mock_llm.generate.assert_called_once()

    # Vérifier le contenu des messages
    call_args = mock_llm.generate.call_args[0][0]
    assert len(call_args) == EXPECTED_MESSAGES_COUNT
    assert call_args[0]["role"] == "system"
    assert "conseiller astrologique" in call_args[0]["content"]
    assert call_args[1]["role"] == "user"
    assert question in call_args[1]["content"]
    assert "precision=5" in call_args[1]["content"]
    assert "eao=" in call_args[1]["content"]


def test_advise_with_tuple_response() -> None:
    """Teste la génération de conseils avec une réponse tuple."""
    mock_retriever = Mock()
    mock_llm = Mock()

    chart = {"chart": {"precision_score": 3}}
    today = {"eao": {"energy": 1, "attention": 2, "opportunity": 1}}
    question = "Quelle est ma journée ?"

    scored_docs = [
        ScoredDocument(doc=Document(id="doc1", text="Document 1"), score=0.8),
        ScoredDocument(doc=Document(id="doc2", text="Document 2"), score=0.7),
    ]

    mock_retriever.query.return_value = scored_docs
    mock_llm.generate.return_value = ("Réponse avec usage", {"tokens": 100})

    orchestrator = ChatOrchestrator(retriever=mock_retriever, llm=mock_llm)

    result_text, result_usage = orchestrator.advise(chart, today, question)

    # Vérifications
    assert result_text == "Réponse avec usage"
    assert result_usage == {"tokens": 100}


def test_advise_with_default_precision() -> None:
    """Teste la génération de conseils avec un score de précision par défaut."""
    mock_retriever = Mock()
    mock_llm = Mock()

    chart = {"chart": {}}  # Pas de precision_score
    today = {"eao": {"energy": 0, "attention": 0, "opportunity": 0}}
    question = "Test question"

    scored_docs = []
    mock_retriever.query.return_value = scored_docs
    mock_llm.generate.return_value = "Réponse"

    orchestrator = ChatOrchestrator(retriever=mock_retriever, llm=mock_llm)

    _result_text, _result_usage = orchestrator.advise(chart, today, question)

    # Vérifier que precision=1 est utilisé par défaut
    call_args = mock_llm.generate.call_args[0][0]
    assert "precision=1" in call_args[1]["content"]


def test_advise_with_empty_context() -> None:
    """Teste la génération de conseils avec un contexte vide."""
    mock_retriever = Mock()
    mock_llm = Mock()

    chart = {"chart": {"precision_score": 2}}
    today = {"eao": {"energy": 1, "attention": 1, "opportunity": 1}}
    question = "Question sans contexte"

    scored_docs = []  # Pas de documents
    mock_retriever.query.return_value = scored_docs
    mock_llm.generate.return_value = "Réponse sans contexte"

    orchestrator = ChatOrchestrator(retriever=mock_retriever, llm=mock_llm)

    _result_text, _result_usage = orchestrator.advise(chart, today, question)

    # Vérifier que le contexte est vide
    call_args = mock_llm.generate.call_args[0][0]
    assert "Context:\n" in call_args[1]["content"]
    # Le contexte devrait être vide (juste "Context:\n")


def test_advise_with_multiple_documents() -> None:
    """Teste la génération de conseils avec plusieurs documents."""
    mock_retriever = Mock()
    mock_llm = Mock()

    chart = {"chart": {"precision_score": 4}}
    today = {"eao": {"energy": 3, "attention": 2, "opportunity": 1}}
    question = "Question complexe"

    scored_docs = [
        ScoredDocument(doc=Document(id=f"doc{i}", text=f"Document {i}"), score=0.9 - i * 0.1)
        for i in range(4)
    ]

    mock_retriever.query.return_value = scored_docs
    mock_llm.generate.return_value = "Réponse complexe"

    orchestrator = ChatOrchestrator(retriever=mock_retriever, llm=mock_llm)

    _result_text, _result_usage = orchestrator.advise(chart, today, question)

    # Vérifier que tous les documents sont dans le contexte
    call_args = mock_llm.generate.call_args[0][0]
    content = call_args[1]["content"]
    assert "- Document 0" in content
    assert "- Document 1" in content
    assert "- Document 2" in content
    assert "- Document 3" in content


def test_advise_query_parameters() -> None:
    """Teste que les paramètres de requête sont corrects."""
    mock_retriever = Mock()
    mock_llm = Mock()

    chart = {"chart": {"precision_score": 5}}
    today = {"eao": {"energy": 1, "attention": 1, "opportunity": 1}}
    question = "Test query"

    scored_docs = [ScoredDocument(doc=Document(id="doc1", text="Doc"), score=0.8)]
    mock_retriever.query.return_value = scored_docs
    mock_llm.generate.return_value = "Response"

    orchestrator = ChatOrchestrator(retriever=mock_retriever, llm=mock_llm)

    orchestrator.advise(chart, today, question)

    # Vérifier que query a été appelé avec les bons paramètres
    mock_retriever.query.assert_called_once()
    query_arg = mock_retriever.query.call_args[0][0]
    assert query_arg.text == question
    assert query_arg.k == DEFAULT_K_VALUE
