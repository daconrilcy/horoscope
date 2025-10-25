"""Tests pour les feature flags.

Ce module teste le comportement des feature flags et leur configuration via les variables
d'environnement.
"""

from __future__ import annotations

from backend.config import flags as f
from backend.core.constants import (
    TEST_METRICS_SHADOW_SAMPLE_RATE,
)

# Constantes pour éviter les valeurs magiques
DEFAULT_SHADOW_SAMPLE_RATE = 0.25
FALLBACK_SHADOW_SAMPLE_RATE = 0.75


def test_shadow_sample_rate_bounds(monkeypatch) -> None:
    """Teste que le taux d'échantillonnage shadow est borné entre 0 et 1."""
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", "-1")
    assert f.shadow_sample_rate() == 0.0
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", "2")
    assert f.shadow_sample_rate() == 1.0
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", "0.5")
    assert f.shadow_sample_rate() == TEST_METRICS_SHADOW_SAMPLE_RATE


def test_shadow_sample_rate_exception_handling(monkeypatch) -> None:
    """Teste la gestion d'exception pour le taux d'échantillonnage invalide."""
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", "invalid")
    assert f.shadow_sample_rate() == DEFAULT_SHADOW_SAMPLE_RATE


def test_shadow_sample_rate_fallback_env_var(monkeypatch) -> None:
    """Teste le fallback vers RETRIEVAL_SHADOW_SAMPLE_RATE."""
    monkeypatch.delenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", raising=False)
    monkeypatch.setenv("RETRIEVAL_SHADOW_SAMPLE_RATE", "0.75")
    assert f.shadow_sample_rate() == FALLBACK_SHADOW_SAMPLE_RATE


def test_shadow_sample_rate_default(monkeypatch) -> None:
    """Teste la valeur par défaut.

    Teste la valeur par défaut quand aucune variable d'environnement n'est définie.
    """
    monkeypatch.delenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", raising=False)
    monkeypatch.delenv("RETRIEVAL_SHADOW_SAMPLE_RATE", raising=False)
    assert f.shadow_sample_rate() == DEFAULT_SHADOW_SAMPLE_RATE


def test_tenant_allowlist_parse(monkeypatch) -> None:
    """Teste que la liste d'autorisation des tenants est parsée correctement."""
    monkeypatch.setenv("RETRIEVAL_TENANT_ALLOWLIST", "a, b ,c,, ")
    vals = f.tenant_allowlist()
    assert vals == {"a", "b", "c"}


def test_dual_write_flag(monkeypatch) -> None:
    """Teste que le flag de dual-write fonctionne correctement."""
    monkeypatch.delenv("FF_RETRIEVAL_DUAL_WRITE", raising=False)
    monkeypatch.delenv("RETRIEVAL_DUAL_WRITE", raising=False)
    assert f.ff_retrieval_dual_write() is False
    monkeypatch.setenv("FF_RETRIEVAL_DUAL_WRITE", "true")
    assert f.ff_retrieval_dual_write() is True


def test_dual_write_flag_variations(monkeypatch) -> None:
    """Teste différentes variations de valeurs truthy pour dual-write."""
    for truthy_val in ["1", "TRUE", "YES", "ON"]:
        monkeypatch.setenv("FF_RETRIEVAL_DUAL_WRITE", truthy_val)
        assert f.ff_retrieval_dual_write() is True

    for falsy_val in ["0", "false", "no", "off", "invalid"]:
        monkeypatch.setenv("FF_RETRIEVAL_DUAL_WRITE", falsy_val)
        assert f.ff_retrieval_dual_write() is False


def test_dual_write_flag_fallback_env_var(monkeypatch) -> None:
    """Teste le fallback vers RETRIEVAL_DUAL_WRITE."""
    monkeypatch.delenv("FF_RETRIEVAL_DUAL_WRITE", raising=False)
    monkeypatch.setenv("RETRIEVAL_DUAL_WRITE", "true")
    assert f.ff_retrieval_dual_write() is True


def test_shadow_read_flag(monkeypatch) -> None:
    """Teste que le flag de shadow-read fonctionne correctement."""
    monkeypatch.delenv("FF_RETRIEVAL_SHADOW_READ", raising=False)
    monkeypatch.delenv("RETRIEVAL_SHADOW_READ", raising=False)
    assert f.ff_retrieval_shadow_read() is False
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_READ", "true")
    assert f.ff_retrieval_shadow_read() is True


def test_shadow_read_flag_fallback_env_var(monkeypatch) -> None:
    """Teste le fallback vers RETRIEVAL_SHADOW_READ."""
    monkeypatch.delenv("FF_RETRIEVAL_SHADOW_READ", raising=False)
    monkeypatch.setenv("RETRIEVAL_SHADOW_READ", "true")
    assert f.ff_retrieval_shadow_read() is True


def test_dual_write_flag_fallback_settings() -> None:
    """Teste le fallback vers les settings du container pour dual-write."""
    from unittest.mock import patch

    with patch("backend.config.flags.container") as mock_container:
        # Test avec setting bool True
        mock_container.settings.RETRIEVAL_DUAL_WRITE = True
        assert f.ff_retrieval_dual_write() is True

        # Test avec setting bool False
        mock_container.settings.RETRIEVAL_DUAL_WRITE = False
        assert f.ff_retrieval_dual_write() is False

        # Test avec setting string truthy
        mock_container.settings.RETRIEVAL_DUAL_WRITE = "true"
        assert f.ff_retrieval_dual_write() is True

        # Test avec setting string falsy
        mock_container.settings.RETRIEVAL_DUAL_WRITE = "false"
        assert f.ff_retrieval_dual_write() is False

        # Test avec setting None
        mock_container.settings.RETRIEVAL_DUAL_WRITE = None
        assert f.ff_retrieval_dual_write() is False


def test_shadow_read_flag_fallback_settings() -> None:
    """Teste le fallback vers les settings du container pour shadow-read."""
    from unittest.mock import patch

    with patch("backend.config.flags.container") as mock_container:
        # Test avec setting bool True
        mock_container.settings.RETRIEVAL_SHADOW_READ = True
        assert f.ff_retrieval_shadow_read() is True

        # Test avec setting bool False
        mock_container.settings.RETRIEVAL_SHADOW_READ = False
        assert f.ff_retrieval_shadow_read() is False

        # Test avec setting string truthy
        mock_container.settings.RETRIEVAL_SHADOW_READ = "yes"
        assert f.ff_retrieval_shadow_read() is True

        # Test avec setting string falsy
        mock_container.settings.RETRIEVAL_SHADOW_READ = "no"
        assert f.ff_retrieval_shadow_read() is False


def test_dual_write_flag_settings_exception() -> None:
    """Teste la gestion d'exception lors de l'accès aux settings."""
    from unittest.mock import patch

    with patch("backend.config.flags.container") as mock_container:
        # Simuler une exception lors de l'accès aux settings
        mock_container.settings = None
        assert f.ff_retrieval_dual_write() is False


def test_shadow_read_flag_settings_exception() -> None:
    """Teste la gestion d'exception lors de l'accès aux settings."""
    from unittest.mock import patch

    with patch("backend.config.flags.container") as mock_container:
        # Simuler une exception lors de l'accès aux settings
        mock_container.settings = None
        assert f.ff_retrieval_shadow_read() is False


def test_tenant_allowlist_empty() -> None:
    """Teste la liste d'autorisation des tenants vide."""
    from unittest.mock import patch

    with patch.dict("os.environ", {}, clear=True):
        vals = f.tenant_allowlist()
        assert vals == set()


def test_tenant_allowlist_single_tenant() -> None:
    """Teste la liste d'autorisation avec un seul tenant."""
    from unittest.mock import patch

    with patch.dict("os.environ", {"RETRIEVAL_TENANT_ALLOWLIST": "tenant1"}):
        vals = f.tenant_allowlist()
        assert vals == {"tenant1"}


def test_tenant_allowlist_whitespace_handling() -> None:
    """Teste la gestion des espaces dans la liste d'autorisation."""
    from unittest.mock import patch

    with patch.dict("os.environ", {"RETRIEVAL_TENANT_ALLOWLIST": "  tenant1  ,  tenant2  ,  "}):
        vals = f.tenant_allowlist()
        assert vals == {"tenant1", "tenant2"}
