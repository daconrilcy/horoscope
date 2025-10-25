"""
Tests pour les routes de chat.

Ce module teste les endpoints de chat, les conseils astrologiques et la gestion des tokens.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from backend.api.routes_chat import estimate_tokens

# Constantes pour éviter les erreurs PLR2004 (Magic values)
EXPECTED_COUNT_2 = 2
EXPECTED_COUNT_3 = 3
EXPECTED_COUNT_5 = 5
TOKEN_COUNT_150 = 150
TOKEN_COUNT_100 = 100


def test_estimate_tokens_api_strategy() -> None:
    """Teste l'estimation de tokens avec la stratégie API."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = "api"

        # Test avec usage valide
        usage = {"total_tokens": 150}
        result = estimate_tokens("test text", "gpt-4", usage)
        assert result  == TOKEN_COUNT_150

        # Test avec usage invalide (fallback vers words)
        usage_invalid = {"total_tokens": "invalid"}
        result = estimate_tokens("test text", "gpt-4", usage_invalid)
        assert result  == EXPECTED_COUNT_2  # "test text" = 2 mots


def test_estimate_tokens_tiktoken_strategy() -> None:
    """Teste l'estimation de tokens avec la stratégie tiktoken."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = "tiktoken"

        with patch("backend.api.routes_chat.tiktoken") as mock_tiktoken:
            mock_encoding = Mock()
            mock_encoding.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens
            mock_tiktoken.encoding_for_model.return_value = mock_encoding

            result = estimate_tokens("test text", "gpt-4", None)
            assert result  == EXPECTED_COUNT_5


def test_estimate_tokens_tiktoken_fallback() -> None:
    """Teste le fallback de tiktoken vers words."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = "tiktoken"

        with patch("backend.api.routes_chat.tiktoken") as mock_tiktoken:
            mock_tiktoken.encoding_for_model.side_effect = Exception("Encoding error")

            result = estimate_tokens("test text", "gpt-4", None)
            assert result  == EXPECTED_COUNT_2  # fallback vers words


def test_estimate_tokens_words_strategy() -> None:
    """Teste l'estimation de tokens avec la stratégie words."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = "words"

        result = estimate_tokens("hello world test", "gpt-4", None)
        assert result  == EXPECTED_COUNT_3


def test_estimate_tokens_auto_strategy() -> None:
    """Teste l'estimation de tokens avec la stratégie auto."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = "auto"

        # Test avec usage disponible (priorité API)
        usage = {"total_tokens": 100}
        result = estimate_tokens("test", "gpt-4", usage)
        assert result  == TOKEN_COUNT_100


def test_estimate_tokens_empty_text() -> None:
    """Teste l'estimation de tokens avec un texte vide."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = "words"

        result = estimate_tokens("", "gpt-4", None)
        assert result == 0


def test_estimate_tokens_none_text() -> None:
    """Teste l'estimation de tokens avec un texte None."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = "words"

        result = estimate_tokens(None, "gpt-4", None)
        assert result == 0


def test_estimate_tokens_default_model_encoding() -> None:
    """Teste l'estimation de tokens avec l'encodage par défaut."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = "tiktoken"

        with patch("backend.api.routes_chat.tiktoken") as mock_tiktoken:
            mock_encoding = Mock()
            mock_encoding.encode.return_value = [1, 2, 3]  # 3 tokens
            mock_tiktoken.get_encoding.return_value = mock_encoding

            result = estimate_tokens("test text", None, None)
            assert result  == EXPECTED_COUNT_3
            mock_tiktoken.get_encoding.assert_called_with("cl100k_base")


def test_estimate_tokens_strategy_none() -> None:
    """Teste l'estimation de tokens avec une stratégie None."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = None

        result = estimate_tokens("hello world", "gpt-4", None)
        assert result  == EXPECTED_COUNT_2  # fallback vers words


def test_estimate_tokens_strategy_empty() -> None:
    """Teste l'estimation de tokens avec une stratégie vide."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = ""

        result = estimate_tokens("hello world", "gpt-4", None)
        assert result  == EXPECTED_COUNT_2  # fallback vers words


def test_estimate_tokens_usage_float() -> None:
    """Teste l'estimation de tokens avec usage contenant un float."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = "api"

        usage = {"total_tokens": 150.5}
        result = estimate_tokens("test text", "gpt-4", usage)
        assert result  == TOKEN_COUNT_150  # converti en int


def test_estimate_tokens_usage_none() -> None:
    """Teste l'estimation de tokens avec usage None."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = "api"

        result = estimate_tokens("test text", "gpt-4", None)
        assert result  == EXPECTED_COUNT_2  # fallback vers words


def test_estimate_tokens_usage_invalid_type() -> None:
    """Teste l'estimation de tokens avec usage de type invalide."""
    with patch("backend.api.routes_chat.get_settings") as mock_settings:
        mock_settings.return_value.TOKEN_COUNT_STRATEGY = "api"

        usage = {"total_tokens": "not_a_number"}
        result = estimate_tokens("test text", "gpt-4", usage)
        assert result  == EXPECTED_COUNT_2  # fallback vers words
