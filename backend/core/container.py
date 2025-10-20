import os

from backend.core.settings import get_settings
from backend.infra.astro.internal_astro import InternalAstroEngine
from backend.infra.content_repo import JSONContentRepository
from backend.infra.repositories import (
    InMemoryChartRepo,
    InMemoryUserRepo,
    RedisChartRepo,
    RedisUserRepo,
)
from backend.infra.secrets.vault_client import VaultClient


class Container:
    def __init__(self):
        self.settings = get_settings()
        base_dir = os.path.dirname(__file__)
        infra_dir = os.path.normpath(os.path.join(base_dir, "..", "infra"))
        content_path = os.path.join(infra_dir, "content.json")
        self.content_repo = JSONContentRepository(path=content_path)
        self.astro = InternalAstroEngine(seed=self.settings.ASTRO_SEED)
        # Secrets/Vault
        self.vault = VaultClient(enabled=getattr(self.settings, "VAULT_ENABLED", False))
        if self.settings.REDIS_URL:
            try:
                self.chart_repo = RedisChartRepo(self.settings.REDIS_URL)
                self.storage_backend = "redis"
            except Exception as err:
                if getattr(self.settings, "REQUIRE_REDIS", False):
                    raise RuntimeError("Redis required but unavailable") from err
                self.chart_repo = InMemoryChartRepo()
                self.storage_backend = "memory-fallback"
        else:
            if getattr(self.settings, "REQUIRE_REDIS", False):
                raise RuntimeError("Redis required but REDIS_URL not set")
            self.chart_repo = InMemoryChartRepo()
            self.storage_backend = "memory"

        # users
        if self.settings.REDIS_URL:
            try:
                self.user_repo = RedisUserRepo(self.settings.REDIS_URL)
            except Exception as err:
                if getattr(self.settings, "REQUIRE_REDIS", False):
                    raise RuntimeError("Redis required but unavailable") from err
                self.user_repo = InMemoryUserRepo()
        else:
            self.user_repo = InMemoryUserRepo()

    def resolve_secret(self, key: str) -> str:
        """Instance-level secret resolution: Vault → env → settings.

        Ne journalise jamais la valeur du secret.
        """
        if getattr(self, "vault", None) and self.vault.enabled:
            val = self.vault.get_secret(key)
            if val:
                return val
        env_val = os.getenv(key)
        if env_val:
            return env_val
        return getattr(self.settings, key, "") or ""


container = Container()
"""
Conteneur d'injection de dépendances et configuration application.

Instancie les composants centraux (settings, dépôts, moteur astro, etc.)
et expose un singleton `container` utilisé par le reste de l'application.
"""


def _env_or_settings(key: str, settings) -> str:
    """Retourne d'abord l'env, sinon l'attribut dans settings, sinon chaîne vide.

    Ne loggue jamais la valeur du secret.
    """
    val = os.getenv(key)
    if val:
        return val
    return getattr(settings, key, "") or ""


def _try_vault(container: Container, key: str) -> str:
    if getattr(container, "vault", None) and container.vault.enabled:
        val = container.vault.get_secret(key)
        if val:
            return val
    return ""


def resolve_secret(key: str) -> str:
    """Résout un secret via Vault avec fallback env/settings.

    Ordre: Vault (si activé) → env → settings. Ne journalise jamais de valeurs.
    """
    # Try Vault first
    from backend.core.container import container as _container  # local import to avoid cycles

    val = _try_vault(_container, key)
    if val:
        return val
    # Fallback
    return _env_or_settings(key, _container.settings)
