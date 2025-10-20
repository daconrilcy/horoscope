"""Définition et chargement des paramètres de configuration applicative.

Objectif du module
------------------
- Centraliser les paramètres (env/.env) via Pydantic Settings
- Résoudre le fichier `.env` à utiliser selon la stratégie: ENV_FILE > .env.{APP_ENV} > .env
"""

import os
from pathlib import Path

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

# Détermination du fichier .env à utiliser avec priorité:
# 1) ENV_FILE (chemin explicite)
# 2) .env.{APP_ENV} si présent
# 3) .env (défaut)
_cwd = Path.cwd()
_env_file_from_env = os.getenv("ENV_FILE")
if _env_file_from_env:
    _ENV_FILE_PATH = _env_file_from_env
else:
    _app_env = os.getenv("APP_ENV", "dev")
    _candidate_specific = _cwd / f".env.{_app_env}"
    _candidate_default = _cwd / ".env"
    if _candidate_specific.exists():
        _ENV_FILE_PATH = _candidate_specific
    elif _candidate_default.exists():
        _ENV_FILE_PATH = _candidate_default
    else:
        _ENV_FILE_PATH = _candidate_default


class Settings(BaseSettings):
    """Modèle de configuration chargé depuis l'environnement et .env."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE_PATH,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
    )
    APP_NAME: str = "horoscope-backend"
    APP_ENV: str = "dev"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    CORS_ORIGINS: list[AnyHttpUrl] | list[str] = []
    DATABASE_URL: str | None = None
    REDIS_URL: str | None = None
    REQUIRE_REDIS: bool = False
    ASTRO_SEED: int | None = None
    # JWT/Auth
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALG: str = "HS256"
    JWT_EXPIRES_MIN: int = 60

    # Phase 3 settings
    OPENAI_API_KEY: str | None = None
    EMBEDDINGS_PROVIDER: str = "openai"  # "openai" | "local"
    EMBEDDINGS_MODEL: str = "text-embedding-3-small"
    LOCAL_EMBEDDINGS_MODEL: str = "all-MiniLM-L6-v2"
    VECTOR_BACKEND: str = "faiss"  # "faiss" | "elasticsearch"
    OTLP_ENDPOINT: str | None = None
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # Vault/Sécurité
    VAULT_ENABLED: bool = False
    # LLM Guard
    LLM_GUARD_ENABLE: bool = True
    LLM_GUARD_MAX_INPUT_LEN: int = 1000
    # Rate limit & budgets
    RATE_LIMIT_TENANT_QPS: int = 5
    TENANT_DEFAULT_BUDGET_USD: float = 0.0
    TENANT_BUDGETS_JSON: str = "{}"
    RATE_LIMIT_EXEMPT_HEALTH: bool = False
    # Celery Ops
    CELERY_MAX_FAILURES_BEFORE_DLQ: int = 3
    # Token counting strategy: auto | api | tiktoken | words
    TOKEN_COUNT_STRATEGY: str = "auto"
    # Limitation de cardinalité des labels métriques (CSV via .env, peut être vide)
    ALLOWED_LLM_MODELS: list[str] = []
    ALLOWED_TENANTS: list[str] = []


def get_settings() -> Settings:
    """Construit et retourne la configuration de l'application."""
    return Settings()
