"""Définition et chargement des paramètres de configuration applicative.

Objectif du module
------------------
- Centraliser les paramètres (env/.env) via Pydantic Settings.
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


def get_settings() -> Settings:
    """Construit et retourne la configuration de l'application."""
    return Settings()
