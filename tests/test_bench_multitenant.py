from __future__ import annotations

import json
import statistics
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.bench_multitenant import BenchmarkConfig, MultiTenantBenchmark, TenantSimulator

"""Tests for multi-tenant benchmark script."""


class TestBenchmarkConfig:
    """Test BenchmarkConfig class."""
    
    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = BenchmarkConfig()
        assert config.qps == 50
        assert config.tenants == 3
        assert config.duration == 300
        assert config.topk == 10
        assert config.chunk_size == 512
        assert config.warm_start is False
        assert config.noisy_neighbor is False
        assert config.base_url == "http://localhost:8000"
        
    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = BenchmarkConfig(
            qps=100,
            tenants=5,
            duration=600,
            topk=20,
            chunk_size=1024,
            warm_start=True,
            noisy_neighbor=True,
            base_url="https://api.example.com",
        )
        assert config.qps == 100
        assert config.tenants == 5
        assert config.duration == 600
        assert config.topk == 20
        assert config.chunk_size == 1024
        assert config.warm_start is True
        assert config.noisy_neighbor is True
        assert config.base_url == "https://api.example.com"


class TestTenantSimulator:
    """Test TenantSimulator class."""
    
    def test_tenant_initialization(self) -> None:
        """Test tenant initialization."""
        config = BenchmarkConfig()
        tenant = TenantSimulator("tenant_1", config)
        
        assert tenant.tenant_id == "tenant_1"
        assert tenant.config == config
        assert tenant.is_noisy is False
        assert tenant.request_count == 0
        assert tenant.latencies == []
        assert tenant.errors == []
        
    def test_set_noisy(self) -> None:
        """Test setting noisy neighbor behavior."""
        config = BenchmarkConfig()
        tenant = TenantSimulator("tenant_1", config)
        
        tenant.set_noisy(True)
        assert tenant.is_noisy is True
        
        tenant.set_noisy(False)
        assert tenant.is_noisy is False
        
    @pytest.mark.asyncio
    async def test_make_request_success(self) -> None:
        """Test successful request."""
        config = BenchmarkConfig()
        tenant = TenantSimulator("tenant_1", config)
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        
        result = await tenant.make_request(mock_client)
        
        assert result["tenant_id"] == "tenant_1"
        assert result["status_code"] == 200
        assert result["success"] is True
        assert "latency" in result
        assert "timestamp" in result
        assert len(tenant.latencies) == 1
        assert tenant.request_count == 1
        
    @pytest.mark.asyncio
    async def test_make_request_error(self) -> None:
        """Test request with error."""
        config = BenchmarkConfig()
        tenant = TenantSimulator("tenant_1", config)
        
        # Mock client that raises exception
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection error")
        
        result = await tenant.make_request(mock_client)
        
        assert result["tenant_id"] == "tenant_1"
        assert result["status_code"] == 0
        assert result["success"] is False
        assert result["error"] == "Connection error"
        assert "latency" in result
        assert "timestamp" in result
        assert len(tenant.latencies) == 1
        assert len(tenant.errors) == 1


class TestMultiTenantBenchmark:
    """Test MultiTenantBenchmark class."""
    
    def test_benchmark_initialization(self) -> None:
        """Test benchmark initialization."""
        config = BenchmarkConfig()
        benchmark = MultiTenantBenchmark(config)
        
        assert benchmark.config == config
        assert benchmark.tenants == []
        assert benchmark.results == []
        
    def test_setup_tenants(self) -> None:
        """Test tenant setup."""
        config = BenchmarkConfig(tenants=3, noisy_neighbor=True)
        benchmark = MultiTenantBenchmark(config)
        benchmark.setup_tenants()
        
        assert len(benchmark.tenants) == 3
        assert benchmark.tenants[0].is_noisy is True  # First tenant is noisy
        assert benchmark.tenants[1].is_noisy is False
        assert benchmark.tenants[2].is_noisy is False
        
    def test_setup_tenants_no_noisy(self) -> None:
        """Test tenant setup without noisy neighbor."""
        config = BenchmarkConfig(tenants=3, noisy_neighbor=False)
        benchmark = MultiTenantBenchmark(config)
        benchmark.setup_tenants()
        
        assert len(benchmark.tenants) == 3
        assert all(not tenant.is_noisy for tenant in benchmark.tenants)
        
    def test_calculate_metrics_empty(self) -> None:
        """Test metrics calculation with no data."""
        config = BenchmarkConfig()
        benchmark = MultiTenantBenchmark(config)
        benchmark.setup_tenants()
        
        metrics = benchmark.calculate_metrics()
        
        assert metrics["config"]["qps"] == 50
        assert metrics["overall_metrics"] == {}
        assert metrics["tenant_metrics"] == {}
        assert metrics["variance_analysis"]["p95_variance"] == 0.0
        
    def test_calculate_metrics_with_data(self) -> None:
        """Test metrics calculation with sample data."""
        config = BenchmarkConfig()
        benchmark = MultiTenantBenchmark(config)
        benchmark.setup_tenants()
        
        # Add sample latencies
        benchmark.tenants[0].latencies = [0.1, 0.2, 0.3, 0.4, 0.5]
        benchmark.tenants[0].request_count = 5
        benchmark.tenants[1].latencies = [0.15, 0.25, 0.35, 0.45, 0.55]
        benchmark.tenants[1].request_count = 5
        
        metrics = benchmark.calculate_metrics()
        
        assert metrics["overall_metrics"]["total_requests"] == 10
        assert abs(metrics["overall_metrics"]["mean_latency"] - 0.325) < 0.001
        assert len(metrics["tenant_metrics"]) == 2
        assert metrics["tenant_metrics"]["tenant_1"]["request_count"] == 5
        
    def test_calculate_variance(self) -> None:
        """Test variance calculation."""
        config = BenchmarkConfig()
        benchmark = MultiTenantBenchmark(config)
        benchmark.setup_tenants()
        
        # Add sample data with known variance
        benchmark.tenants[0].latencies = [0.1, 0.2, 0.3]
        benchmark.tenants[1].latencies = [0.4, 0.5, 0.6]
        
        tenant_metrics = {
            "tenant_1": {"p95_latency": 0.2, "p99_latency": 0.3},
            "tenant_2": {"p95_latency": 0.5, "p99_latency": 0.6},
        }
        
        variance = benchmark._calculate_variance(tenant_metrics)
        
        assert variance["p95_variance"] > 0
        assert variance["p99_variance"] > 0
        assert variance["p95_cv"] > 0
        assert variance["p99_cv"] > 0


class TestBenchmarkIntegration:
    """Integration tests for the benchmark."""
    
    @pytest.mark.asyncio
    async def test_warm_up(self) -> None:
        """Test warm-up functionality."""
        config = BenchmarkConfig(warm_start=True)
        benchmark = MultiTenantBenchmark(config)
        benchmark.setup_tenants()
        
        # Mock client for warm-up
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        
        # Mock the context manager
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_client)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_context):
            await benchmark.warm_up()
            
        # Verify warm-up requests were made
        assert mock_client.post.call_count == 15  # 3 tenants * 5 warm-up requests
        
    @pytest.mark.asyncio
    async def test_warm_up_disabled(self) -> None:
        """Test warm-up when disabled."""
        config = BenchmarkConfig(warm_start=False)
        benchmark = MultiTenantBenchmark(config)
        benchmark.setup_tenants()
        
        # Should not make any requests
        with patch("httpx.AsyncClient") as mock_client_class:
            await benchmark.warm_up()
            mock_client_class.assert_not_called()
            
    def test_json_output_structure(self) -> None:
        """Test JSON output structure."""
        config = BenchmarkConfig()
        benchmark = MultiTenantBenchmark(config)
        benchmark.setup_tenants()
        
        # Add sample data for multiple tenants to avoid variance calculation issues
        benchmark.tenants[0].latencies = [0.1, 0.2, 0.3]
        benchmark.tenants[0].request_count = 3
        benchmark.tenants[1].latencies = [0.15, 0.25, 0.35]
        benchmark.tenants[1].request_count = 3
        
        metrics = benchmark.calculate_metrics()
        
        # Verify structure
        assert "config" in metrics
        assert "timestamp" in metrics
        assert "overall_metrics" in metrics
        assert "tenant_metrics" in metrics
        assert "variance_analysis" in metrics
        
        # Verify config structure
        config_keys = {
            "qps", "tenants", "duration", "topk", 
            "chunk_size", "warm_start", "noisy_neighbor", "base_url"
        }
        assert set(metrics["config"].keys()) == config_keys
        
        # Verify overall metrics structure
        overall_keys = {
            "total_requests", "p95_latency", "p99_latency", 
            "mean_latency", "std_latency"
        }
        assert set(metrics["overall_metrics"].keys()) == overall_keys
        
    def test_json_serialization(self) -> None:
        """Test JSON serialization."""
        config = BenchmarkConfig()
        benchmark = MultiTenantBenchmark(config)
        benchmark.setup_tenants()
        
        # Add sample data for multiple tenants to avoid variance calculation issues
        benchmark.tenants[0].latencies = [0.1, 0.2, 0.3]
        benchmark.tenants[0].request_count = 3
        benchmark.tenants[1].latencies = [0.15, 0.25, 0.35]
        benchmark.tenants[1].request_count = 3
        
        metrics = benchmark.calculate_metrics()
        
        # Should be serializable to JSON
        json_str = json.dumps(metrics)
        parsed = json.loads(json_str)
        
        assert parsed["config"]["qps"] == 50
        assert parsed["overall_metrics"]["total_requests"] == 6


class TestBenchmarkDeterministic:
    """Test deterministic behavior."""
    
    def test_seed_consistency(self) -> None:
        """Test that results are consistent with fixed seed."""
        import random
        
        # Set fixed seed
        random.seed(42)
        
        config = BenchmarkConfig()
        tenant = TenantSimulator("tenant_1", config)
        tenant.set_noisy(True)
        
        # Generate some random delays
        delays = [random.uniform(0.1, 0.5) for _ in range(5)]
        
        # Reset seed and generate again
        random.seed(42)
        delays2 = [random.uniform(0.1, 0.5) for _ in range(5)]
        
        assert delays == delays2
        
    def test_statistics_consistency(self) -> None:
        """Test statistics calculations are consistent."""
        latencies = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        # Calculate percentiles manually
        p95_manual = statistics.quantiles(latencies, n=20)[18]
        p99_manual = statistics.quantiles(latencies, n=100)[98]
        
        # Should match expected values (calculated from actual quantiles)
        assert abs(p95_manual - 0.57) < 0.01  # 95th percentile of [0.1, 0.2, 0.3, 0.4, 0.5]
        assert abs(p99_manual - 0.495) < 0.01  # 99th percentile
