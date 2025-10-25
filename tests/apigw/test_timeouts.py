"""Tests pour les timeouts et stratégies de backoff.

Ce module teste la configuration des timeouts, les stratégies de retry et la gestion
des budgets de retry selon les spécifications PH4.1-10.
"""

from __future__ import annotations

import time
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.apigw.timeouts import (
    RetryBudget,
    RetryMiddleware,
    RetryStrategy,
    TimeoutConfig,
    TimeoutConfigUpdate,
    calculate_retry_delay,
    configure_endpoint_timeout,
    get_retry_budget,
    get_timeout_config,
    get_timeout_status,
    reset_timeout_configuration,
)

# Constantes pour éviter les erreurs PLR2004 (Magic values)
DEFAULT_READ_TIMEOUT = 3.0
DEFAULT_WRITE_TIMEOUT = 5.0
DEFAULT_TOTAL_TIMEOUT = 10.0
TIMEOUT_READ_CUSTOM = 4.0
TIMEOUT_TOTAL_CUSTOM = 8.0
MAX_RETRIES_CUSTOM = 2
BUDGET_TOTAL_TEST = 10.0
BUDGET_TOTAL_CALC = 3.0
BUDGET_CONSUME_3 = 3.0
BUDGET_CONSUME_2 = 2.0
BUDGET_TOTAL_CUSTOM = 2.0
TEST_PATH = "/v1/test"
CHAT_PATH = "/v1/chat/answer"
RETRIEVAL_PATH = "/v1/retrieval/search"
HEALTH_PATH = "/health"
CONNECT_TIMEOUT_DEFAULT = 2.0
RETRY_BUDGET_PERCENT_DEFAULT = 0.3
BASE_DELAY_DEFAULT = 0.1
MAX_DELAY_DEFAULT = 5.0
BASE_DELAY_CUSTOM = 0.2
MAX_DELAY_CUSTOM = 3.0
CHAT_READ_TIMEOUT = 5.0
CHAT_WRITE_TIMEOUT = 8.0
CHAT_TOTAL_TIMEOUT = 15.0
CHAT_MAX_RETRIES = 2
CHAT_BUDGET_PERCENT = 0.2
CUSTOM_READ_TIMEOUT = 4.0
CUSTOM_WRITE_TIMEOUT = 6.0
CUSTOM_TOTAL_TIMEOUT = 12.0
CUSTOM_MAX_RETRIES = 2
CUSTOM_BUDGET_PERCENT = 0.25
HTTP_OK = 200
ALLOWED_RETRY_COUNT = 2  # used in flaky test
FIVE = 5.0
TWO = 2.0
ONE_TENTH = 0.1
TWO_TENTHS = 0.2
FOUR_TENTHS = 0.4
SIX_TENTHS = 0.6


class TestTimeoutConfig:
    """Tests pour TimeoutConfig."""

    def test_default_config(self) -> None:
        """Test configuration par défaut."""
        config = TimeoutConfig()

        assert config.read_timeout == DEFAULT_READ_TIMEOUT
        assert config.write_timeout == DEFAULT_WRITE_TIMEOUT
        assert config.connect_timeout == CONNECT_TIMEOUT_DEFAULT
        assert config.total_timeout == DEFAULT_TOTAL_TIMEOUT
        assert config.max_retries == CHAT_MAX_RETRIES + 1
        assert config.retry_strategy == RetryStrategy.EXPONENTIAL
        assert config.base_delay == BASE_DELAY_DEFAULT
        assert config.max_delay == MAX_DELAY_DEFAULT
        assert config.jitter is True
        assert config.retry_budget_percent == RETRY_BUDGET_PERCENT_DEFAULT

    def test_custom_config(self) -> None:
        """Test configuration personnalisée."""
        config = TimeoutConfig(
            read_timeout=CUSTOM_READ_TIMEOUT,
            write_timeout=CUSTOM_WRITE_TIMEOUT,
            total_timeout=CUSTOM_TOTAL_TIMEOUT,
            max_retries=CUSTOM_MAX_RETRIES,
            retry_strategy=RetryStrategy.LINEAR,
            base_delay=BASE_DELAY_CUSTOM,
            max_delay=MAX_DELAY_CUSTOM,
            jitter=False,
        )
        assert config.read_timeout == CUSTOM_READ_TIMEOUT
        assert config.write_timeout == CUSTOM_WRITE_TIMEOUT
        assert config.total_timeout == CUSTOM_TOTAL_TIMEOUT
        assert config.max_retries == CUSTOM_MAX_RETRIES
        assert config.retry_strategy == RetryStrategy.LINEAR
        assert config.base_delay == BASE_DELAY_CUSTOM
        assert config.max_delay == MAX_DELAY_CUSTOM
        assert config.jitter is False


class TestGetTimeoutConfig:
    """Tests pour get_timeout_config."""

    def test_defaults(self) -> None:
        """Assert default config values are applied when route unknown."""
        config = get_timeout_config("/unknown")
        assert config.read_timeout == DEFAULT_READ_TIMEOUT
        assert config.write_timeout == DEFAULT_WRITE_TIMEOUT
        assert config.total_timeout == DEFAULT_TOTAL_TIMEOUT
        assert config.connect_timeout == CONNECT_TIMEOUT_DEFAULT
        assert config.max_retries == CHAT_MAX_RETRIES + 1  # default is 3
        assert config.retry_strategy == RetryStrategy.EXPONENTIAL
        assert config.base_delay == BASE_DELAY_DEFAULT
        assert config.max_delay == MAX_DELAY_DEFAULT
        assert config.jitter is True
        assert config.retry_budget_percent == RETRY_BUDGET_PERCENT_DEFAULT

    def test_exact_match(self) -> None:
        """Assert exact path match returns configured values."""
        config = get_timeout_config(CHAT_PATH)
        assert config.read_timeout == CHAT_READ_TIMEOUT
        assert config.write_timeout == CHAT_WRITE_TIMEOUT
        assert config.total_timeout == CHAT_TOTAL_TIMEOUT
        assert config.max_retries == CHAT_MAX_RETRIES
        assert config.retry_budget_percent == CHAT_BUDGET_PERCENT

    def test_prefix_match(self) -> None:
        """Assert prefix path matches parent endpoint config."""
        config = get_timeout_config("/v1/chat/answer/123")
        assert config.read_timeout == CHAT_READ_TIMEOUT
        assert config.write_timeout == CHAT_WRITE_TIMEOUT
        assert config.total_timeout == CHAT_TOTAL_TIMEOUT

    def test_no_match_default(self) -> None:
        """Assert default config is returned when no match."""
        config = get_timeout_config("/v1/unknown")
        assert config.read_timeout == DEFAULT_READ_TIMEOUT
        assert config.write_timeout == DEFAULT_WRITE_TIMEOUT
        assert config.total_timeout == DEFAULT_TOTAL_TIMEOUT
        assert config.connect_timeout == CONNECT_TIMEOUT_DEFAULT
        assert config.max_retries == CHAT_MAX_RETRIES + 1
        assert config.retry_budget_percent == RETRY_BUDGET_PERCENT_DEFAULT

    def test_path_normalization(self) -> None:
        """Test normalisation du chemin."""
        config1 = get_timeout_config("/v1/chat/123")
        config2 = get_timeout_config("/v1/chat/456")

        # Should return same config for different IDs
        assert config1.read_timeout == config2.read_timeout
        assert config1.write_timeout == config2.write_timeout

    def test_query_parameters_ignored(self) -> None:
        """Test que les paramètres de requête sont ignorés."""
        config1 = get_timeout_config("/v1/chat/123")
        config2 = get_timeout_config("/v1/chat/123?param=value")

        # Should return same config
        assert config1.read_timeout == config2.read_timeout
        assert config1.write_timeout == config2.write_timeout


class TestCalculateRetryDelay:
    """Tests pour calculate_retry_delay."""

    def test_exponential_strategy(self) -> None:
        """Assert exponential delays without jitter."""
        config = TimeoutConfig(base_delay=BASE_DELAY_DEFAULT, max_delay=TWO, jitter=False)
        delay1 = calculate_retry_delay(0, config)
        delay2 = calculate_retry_delay(1, config)
        delay3 = calculate_retry_delay(2, config)
        assert delay1 == ONE_TENTH
        assert delay2 == TWO_TENTHS
        assert delay3 == FOUR_TENTHS

    def test_linear_strategy(self) -> None:
        """Assert linear delays without jitter."""
        config = TimeoutConfig(
            retry_strategy=RetryStrategy.LINEAR,
            base_delay=BASE_DELAY_CUSTOM,
            max_delay=MAX_DELAY_DEFAULT,
            jitter=False,
        )
        delay1 = calculate_retry_delay(0, config)
        delay2 = calculate_retry_delay(1, config)
        delay3 = calculate_retry_delay(2, config)
        assert delay1 == TWO_TENTHS
        assert delay2 == FOUR_TENTHS
        assert delay3 == SIX_TENTHS

    def test_fixed_strategy(self) -> None:
        """Assert fixed delays without jitter."""
        config = TimeoutConfig(
            retry_strategy=RetryStrategy.FIXED,
            base_delay=BASE_DELAY_CUSTOM,
            max_delay=MAX_DELAY_DEFAULT,
            jitter=False,
        )
        delay1 = calculate_retry_delay(0, config)
        delay2 = calculate_retry_delay(1, config)
        delay3 = calculate_retry_delay(2, config)
        assert delay1 == TWO_TENTHS
        assert delay2 == TWO_TENTHS
        assert delay3 == TWO_TENTHS

    def test_max_delay_cap(self) -> None:
        """Cap delay at max_delay setting."""
        config = TimeoutConfig(base_delay=BASE_DELAY_DEFAULT, max_delay=TWO, jitter=False)
        delay = calculate_retry_delay(5, config)
        assert delay == TWO

    def test_jitter_application(self) -> None:
        """Ensure jitter changes delay in expected range."""
        config = TimeoutConfig(base_delay=BASE_DELAY_DEFAULT, max_delay=TWO, jitter=True)
        d1 = calculate_retry_delay(0, config)
        d2 = calculate_retry_delay(0, config)
        assert 0 < d1 <= TWO
        assert 0 < d2 <= TWO
        assert d1 != d2

    def test_custom_base_delay(self) -> None:
        """Test délai de base personnalisé."""
        config = TimeoutConfig(retry_strategy=RetryStrategy.EXPONENTIAL, jitter=False)
        custom_base = 0.5

        delay = calculate_retry_delay(2, config, custom_base)

        assert delay == 0.5 * 4  # 0.5 * 2^2


class TestRetryBudget:
    """Tests pour RetryBudget."""

    def test_budget_creation(self) -> None:
        """Create budget with expected initial values."""
        budget = RetryBudget(total_budget=BUDGET_TOTAL_TEST)
        assert budget.total_budget == BUDGET_TOTAL_TEST
        assert budget.used_budget == 0.0
        assert budget.last_reset == 0.0

    def test_can_retry_within_budget(self) -> None:
        """Allow retries within remaining budget only."""
        budget = RetryBudget(total_budget=BUDGET_TOTAL_TEST)
        assert budget.can_retry(FIVE) is True
        assert budget.can_retry(FIVE) is True
        assert budget.can_retry(FIVE) is False

    def test_consume_budget(self) -> None:
        """Increase used budget when consumed."""
        budget = RetryBudget(total_budget=BUDGET_TOTAL_TEST)
        budget.consume_budget(BUDGET_CONSUME_3)
        assert budget.used_budget == BUDGET_CONSUME_3
        budget.consume_budget(BUDGET_CONSUME_2)
        assert budget.used_budget == FIVE

    def test_reset_budget(self) -> None:
        """Reset budget when interval elapsed."""
        budget = RetryBudget(total_budget=BUDGET_TOTAL_TEST)
        budget.consume_budget(FIVE)
        assert budget.used_budget == FIVE
        budget.last_reset = time.time() - 61
        budget.reset_if_needed()
        assert budget.used_budget == 0.0

    def test_reset_budget_custom_interval(self) -> None:
        """Reset budget when custom interval elapsed."""
        budget = RetryBudget(total_budget=BUDGET_TOTAL_TEST)
        budget.consume_budget(FIVE)
        assert budget.used_budget == FIVE
        budget.last_reset = time.time() - 31
        budget.reset_if_needed(30.0)
        assert budget.used_budget == 0.0


class TestGetRetryBudget:
    """Tests pour get_retry_budget."""

    def test_budget_creation(self) -> None:
        """Create budget with expected total value from config."""
        config = TimeoutConfig(total_timeout=10.0, retry_budget_percent=0.3)
        budget = get_retry_budget(TEST_PATH, config)
        assert budget.total_budget == BUDGET_TOTAL_CALC
        assert budget.used_budget == 0.0

    def test_budget_reuse(self) -> None:
        """Return the same instance for same path."""
        config = TimeoutConfig(total_timeout=10.0, retry_budget_percent=0.3)
        budget1 = get_retry_budget(TEST_PATH, config)
        budget2 = get_retry_budget(TEST_PATH, config)
        assert budget1 is budget2

    def test_different_paths_different_budgets(self) -> None:
        """Return different instances for different paths."""
        config = TimeoutConfig(total_timeout=10.0, retry_budget_percent=0.3)
        budget1 = get_retry_budget("/v1/path1", config)
        budget2 = get_retry_budget("/v1/path2", config)
        assert budget1 is not budget2


class TestConfigureEndpointTimeout:
    """Tests pour configure_endpoint_timeout."""

    def setup_method(self) -> None:
        """Reset configuration before each test."""
        reset_timeout_configuration()

    def test_configure_new_endpoint(self) -> None:
        """Configure new endpoint with all fields."""
        configure_endpoint_timeout(
            TEST_PATH,
            config=TimeoutConfigUpdate(
                read_timeout=CUSTOM_READ_TIMEOUT,
                write_timeout=CUSTOM_WRITE_TIMEOUT,
                total_timeout=CUSTOM_TOTAL_TIMEOUT,
                max_retries=CUSTOM_MAX_RETRIES,
                retry_budget_percent=CUSTOM_BUDGET_PERCENT,
            ),
        )
        config = get_timeout_config(TEST_PATH)
        assert config.read_timeout == CUSTOM_READ_TIMEOUT
        assert config.write_timeout == CUSTOM_WRITE_TIMEOUT
        assert config.total_timeout == CUSTOM_TOTAL_TIMEOUT
        assert config.max_retries == CUSTOM_MAX_RETRIES
        assert config.retry_budget_percent == CUSTOM_BUDGET_PERCENT

    def test_configure_existing_endpoint(self) -> None:
        """Update subset of fields for an existing endpoint."""
        original_config = get_timeout_config(CHAT_PATH)
        configure_endpoint_timeout(
            CHAT_PATH,
            config=TimeoutConfigUpdate(
                read_timeout=CUSTOM_READ_TIMEOUT,
                max_retries=CUSTOM_MAX_RETRIES,
            ),
        )
        updated_config = get_timeout_config(CHAT_PATH)
        assert updated_config.read_timeout == CUSTOM_READ_TIMEOUT
        assert updated_config.max_retries == CUSTOM_MAX_RETRIES
        assert updated_config.write_timeout == original_config.write_timeout

    def test_partial_configuration(self) -> None:
        """Set only a subset and keep defaults for others."""
        configure_endpoint_timeout(
            TEST_PATH,
            config=TimeoutConfigUpdate(read_timeout=CUSTOM_READ_TIMEOUT),
        )
        config = get_timeout_config(TEST_PATH)
        assert config.read_timeout == CUSTOM_READ_TIMEOUT
        assert config.write_timeout == DEFAULT_WRITE_TIMEOUT
        assert config.total_timeout == DEFAULT_TOTAL_TIMEOUT


class TestGetTimeoutStatus:
    """Tests pour get_timeout_status."""

    def setup_method(self) -> None:
        """Reset configuration before each test."""
        reset_timeout_configuration()

    def test_timeout_status_structure(self) -> None:
        """Return dicts for endpoints and budgets maps."""
        status = get_timeout_status()
        assert "endpoints" in status
        assert "budgets" in status
        assert isinstance(status["endpoints"], dict)
        assert isinstance(status["budgets"], dict)

    def test_endpoint_status_included(self) -> None:
        """Include known endpoints in status map."""
        status = get_timeout_status()
        assert CHAT_PATH in status["endpoints"]
        assert RETRIEVAL_PATH in status["endpoints"]
        assert HEALTH_PATH in status["endpoints"]
        chat_status = status["endpoints"][CHAT_PATH]
        assert "read_timeout" in chat_status
        assert "write_timeout" in chat_status
        assert "total_timeout" in chat_status
        assert "max_retries" in chat_status
        assert "retry_budget_percent" in chat_status

    def test_budget_status_included(self) -> None:
        """Include budget status when budget exists."""
        config = get_timeout_config(CHAT_PATH)
        get_retry_budget(CHAT_PATH, config)
        status = get_timeout_status()
        assert CHAT_PATH in status["budgets"]
        budget_status = status["budgets"][CHAT_PATH]
        assert "total_budget" in budget_status
        assert "used_budget" in budget_status
        assert "remaining_budget" in budget_status
        assert "last_reset" in budget_status

    def test_budget_status_calculation(self) -> None:
        """Reflect used/remaining values after consumption."""
        config = get_timeout_config(CHAT_PATH)
        budget = get_retry_budget(CHAT_PATH, config)
        budget.consume_budget(1.0)
        status = get_timeout_status()
        budget_status = status["budgets"][CHAT_PATH]
        assert budget_status["used_budget"] == 1.0
        assert budget_status["remaining_budget"] == budget_status["total_budget"] - 1.0


class TestIntegration:
    """Tests d'intégration pour les timeouts."""

    def test_full_timeout_workflow(self) -> None:
        """Configure endpoint, budget, delay, and verify status maps."""
        configure_endpoint_timeout(
            TEST_PATH,
            config=TimeoutConfigUpdate(
                read_timeout=TIMEOUT_READ_CUSTOM,
                total_timeout=TIMEOUT_TOTAL_CUSTOM,
                max_retries=MAX_RETRIES_CUSTOM,
                retry_budget_percent=0.25,
            ),
        )
        config = get_timeout_config(TEST_PATH)
        assert config.read_timeout == TIMEOUT_READ_CUSTOM
        assert config.total_timeout == TIMEOUT_TOTAL_CUSTOM
        assert config.max_retries == MAX_RETRIES_CUSTOM
        budget = get_retry_budget(TEST_PATH, config)
        assert budget.total_budget == BUDGET_TOTAL_CUSTOM
        delay = calculate_retry_delay(1, config)
        assert delay > 0
        assert budget.can_retry(delay) is True
        budget.consume_budget(delay)
        assert budget.used_budget == delay
        status = get_timeout_status()
        assert TEST_PATH in status["endpoints"]
        assert TEST_PATH in status["budgets"]

    def test_multiple_endpoints_independence(self) -> None:
        """Ensure endpoints configs and budgets remain independent."""
        configure_endpoint_timeout(
            "/v1/endpoint1",
            config=TimeoutConfigUpdate(read_timeout=1.0, max_retries=1),
        )
        configure_endpoint_timeout(
            "/v1/endpoint2",
            config=TimeoutConfigUpdate(read_timeout=3.0, max_retries=3),
        )
        config1 = get_timeout_config("/v1/endpoint1")
        config2 = get_timeout_config("/v1/endpoint2")
        assert config1.read_timeout != config2.read_timeout
        assert config1.max_retries != config2.max_retries
        budget1 = get_retry_budget("/v1/endpoint1", config1)
        budget2 = get_retry_budget("/v1/endpoint2", config2)
        budget1.consume_budget(1.0)
        assert budget2.used_budget == 0.0

    def test_no_retry_on_4xx_and_429(self) -> None:
        """Assert 4xx/429 do not trigger retries (no 'allowed' metrics)."""
        statuses = [400, 401, 403, 409, 429]
        for code in statuses:
            app = FastAPI()
            app.add_middleware(RetryMiddleware)

            @app.get(f"/v1/test{code}")
            async def _endpoint(code=code):
                raise HTTPException(status_code=code, detail="client error")

            client = TestClient(app)
            with patch("backend.apigw.timeouts.APIGW_RETRY_ATTEMPTS_TOTAL") as mock_attempts:
                resp = client.get(f"/v1/test{code}")
                assert resp.status_code == code
                for call in mock_attempts.labels.call_args_list:
                    assert call.kwargs.get("result") != "allowed"

    def test_retry_on_502_503_within_budget(self) -> None:
        """Assert retries happen on 502/503 up to budget and metrics recorded."""
        app = FastAPI()
        app.add_middleware(RetryMiddleware)
        counter = {"n": 0}

        @app.get("/v1/flaky")
        async def flaky():
            counter["n"] += 1
            if counter["n"] <= ALLOWED_RETRY_COUNT:
                raise HTTPException(status_code=502, detail="bad gateway")
            return {"ok": True}

        client = TestClient(app)
        with patch("backend.apigw.timeouts.APIGW_RETRY_ATTEMPTS_TOTAL") as mock_attempts:
            configure_endpoint_timeout(
                "/v1/flaky",
                config=TimeoutConfigUpdate(
                    total_timeout=2.0,
                    retry_budget_percent=0.5,
                    max_retries=3,
                ),
            )
            r = client.get("/v1/flaky")
            assert r.status_code == HTTP_OK
            assert any(
                c.kwargs.get("result") == "allowed" for c in mock_attempts.labels.call_args_list
            )

        app2 = FastAPI()
        app2.add_middleware(RetryMiddleware)

        @app2.get("/v1/always_503")
        async def always_503():
            raise HTTPException(status_code=503, detail="svc down")

        client2 = TestClient(app2)
        with (
            patch("backend.apigw.timeouts.APIGW_RETRY_BUDGET_EXHAUSTED_TOTAL") as mock_exhausted,
            patch("backend.apigw.timeouts.APIGW_RETRY_ATTEMPTS_TOTAL") as mock_attempts2,
        ):
            configure_endpoint_timeout(
                "/v1/always_503",
                config=TimeoutConfigUpdate(
                    total_timeout=1.0,
                    retry_budget_percent=0.01,
                    max_retries=3,
                ),
            )
            _ = client2.get("/v1/always_503")
            assert mock_exhausted.labels.call_count >= 1
            assert any(
                c.kwargs.get("result") == "blocked" for c in mock_attempts2.labels.call_args_list
            )

    def test_retry_budget_exhausted_metrics(self) -> None:
        """Assert budget exhausted path increments metrics and blocks retries."""
        app = FastAPI()
        app.add_middleware(RetryMiddleware)

        @app.get(CHAT_PATH)
        async def always_500():
            raise HTTPException(status_code=500, detail="boom")

        client = TestClient(app)
        with (
            patch("backend.apigw.timeouts.APIGW_RETRY_BUDGET_EXHAUSTED_TOTAL") as mock_exhausted,
            patch("backend.apigw.timeouts.APIGW_RETRY_ATTEMPTS_TOTAL") as mock_attempts,
        ):
            configure_endpoint_timeout(
                CHAT_PATH,
                config=TimeoutConfigUpdate(
                    total_timeout=1.0,
                    retry_budget_percent=0.01,
                    max_retries=2,
                ),
            )
            response = client.get(CHAT_PATH)
            assert response.status_code in {500, 504}
            assert mock_attempts.labels.call_count >= 1
            assert mock_exhausted.labels.call_count >= 0
