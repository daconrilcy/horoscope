"""Définition et chargement des paramètres de configuration applicative.

Objectif du module
------------------
- Centraliser les paramètres (env/.env) via Pydantic Settings.
"""

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Modèle de configuration chargé depuis l'environnement et .env."""

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, case_sensitive=False)
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
