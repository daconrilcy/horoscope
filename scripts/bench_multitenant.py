"""Script de benchmark multi-tenant avec simulation de voisins bruyants.

Ce script mesure les performances multi-tenant avec contrôle QPS par tenant, scénarios warm/cold
start et simulation de voisins bruyants pour évaluer l'isolation des performances entre tenants.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from backend.core.constants import HTTP_STATUS_OK

"""Multi-tenant benchmark script with noisy neighbor and warm/cold scenarios.

Usage:
  python -m scripts.bench_multitenant --qps 50 --tenants 3 --duration 300 \
      --topk 10 --chunk 512 --warm --noisy-neighbor --output artifacts/bench_multitenant.json

Features:
- QPS control per tenant
- Warm/cold start scenarios
- Noisy neighbor simulation (CPU/IO saturation)
- P95/P99 latency measurements per endpoint
- Variance analysis across tenants
"""

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuration for multi-tenant benchmark."""

    qps: int = 50
    tenants: int = 3
    duration: int = 300
    topk: int = 10
    chunk_size: int = 512
    warm_start: bool = False
    noisy_neighbor: bool = False
    base_url: str = "http://localhost:8000"


class TenantSimulator:
    """Simulates a tenant with configurable behavior."""

    def __init__(self, tenant_id: str, config: BenchmarkConfig) -> None:
        """Initialize tenant simulator."""
        """Initialise un simulateur de tenant.

        Args:
            tenant_id: Identifiant unique du tenant.
            config: Configuration du benchmark.
        """
        self.tenant_id = tenant_id
        self.config = config
        self.is_noisy = False
        self.request_count = 0
        self.latencies: list[float] = []
        self.errors: list[str] = []

    def set_noisy(self, noisy: bool) -> None:
        """Set noisy neighbor behavior."""
        self.is_noisy = noisy

    async def make_request(self, client: httpx.AsyncClient) -> dict[str, Any]:
        """Make a single request to the chat endpoint."""
        start_time = time.time()

        # Simulate noisy neighbor behavior
        if self.is_noisy:
            # Add random CPU/IO delay
            await asyncio.sleep(random.uniform(0.1, 0.5))

        try:
            payload = {
                "query": f"test query from tenant {self.tenant_id}",
                "top_k": self.config.topk,
                "chunk_size": self.config.chunk_size,
            }

            response = await client.post(
                f"{self.config.base_url}/chat/advise",
                json=payload,
                timeout=30.0,
            )

            latency = time.time() - start_time
            self.latencies.append(latency)
            self.request_count += 1

            return {
                "tenant_id": self.tenant_id,
                "latency": latency,
                "status_code": response.status_code,
                "success": response.status_code == HTTP_STATUS_OK,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as exc:
            latency = time.time() - start_time
            self.latencies.append(latency)
            self.errors.append(str(exc))

            return {
                "tenant_id": self.tenant_id,
                "latency": latency,
                "status_code": 0,
                "success": False,
                "error": str(exc),
                "timestamp": datetime.now(UTC).isoformat(),
            }


class MultiTenantBenchmark:
    """Main benchmark orchestrator."""

    def __init__(self, config: BenchmarkConfig) -> None:
        """Initialize multi-tenant benchmark orchestrator."""
        """Initialise l'orchestrateur de benchmark multi-tenant.

        Args:
            config: Configuration du benchmark.
        """
        self.config = config
        self.tenants: list[TenantSimulator] = []
        self.results: list[dict[str, Any]] = []

    def setup_tenants(self) -> None:
        """Initialize tenant simulators."""
        for i in range(self.config.tenants):
            tenant_id = f"tenant_{i + 1}"
            tenant = TenantSimulator(tenant_id, self.config)

            # Make one tenant noisy if requested
            if self.config.noisy_neighbor and i == 0:
                tenant.set_noisy(True)

            self.tenants.append(tenant)

    async def warm_up(self) -> None:
        """Perform warm-up requests if enabled."""
        if not self.config.warm_start:
            return

        log.info("Performing warm-up requests...")
        async with httpx.AsyncClient() as client:
            warm_up_tasks = []
            for tenant in self.tenants:
                for _ in range(5):  # 5 warm-up requests per tenant
                    warm_up_tasks.append(tenant.make_request(client))

            await asyncio.gather(*warm_up_tasks, return_exceptions=True)

        # Clear warm-up data
        for tenant in self.tenants:
            tenant.latencies.clear()
            tenant.errors.clear()
            tenant.request_count = 0

    async def run_benchmark(self) -> None:
        """Run the main benchmark."""
        log.info(
            f"Starting benchmark: {self.config.qps} QPS, "
            f"{self.config.tenants} tenants, {self.config.duration}s"
        )

        async with httpx.AsyncClient() as client:
            start_time = time.time()
            end_time = start_time + self.config.duration

            # Calculate request interval per tenant
            interval_per_tenant = 1.0 / (self.config.qps / self.config.tenants)

            while time.time() < end_time:
                tasks = []
                for tenant in self.tenants:
                    tasks.append(tenant.make_request(client))

                # Wait for all requests to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                self.results.extend([r for r in results if isinstance(r, dict)])

                # Wait for next interval
                await asyncio.sleep(interval_per_tenant)

    def calculate_metrics(self) -> dict[str, Any]:
        """Calculate P95/P99 metrics and variance."""
        all_latencies = []
        tenant_metrics = {}

        for tenant in self.tenants:
            if tenant.latencies:
                latencies = tenant.latencies
                all_latencies.extend(latencies)

                tenant_metrics[tenant.tenant_id] = {
                    "request_count": tenant.request_count,
                    "error_count": len(tenant.errors),
                    "p95_latency": statistics.quantiles(latencies, n=20)[18],  # 95th percentile
                    "p99_latency": statistics.quantiles(latencies, n=100)[98],  # 99th percentile
                    "mean_latency": statistics.mean(latencies),
                    "std_latency": (statistics.stdev(latencies) if len(latencies) > 1 else 0.0),
                    "is_noisy": tenant.is_noisy,
                }

        # Overall metrics
        overall_metrics = {}
        if all_latencies:
            overall_metrics = {
                "total_requests": len(all_latencies),
                "p95_latency": statistics.quantiles(all_latencies, n=20)[18],
                "p99_latency": statistics.quantiles(all_latencies, n=100)[98],
                "mean_latency": statistics.mean(all_latencies),
                "std_latency": (statistics.stdev(all_latencies) if len(all_latencies) > 1 else 0.0),
            }

        return {
            "config": {
                "qps": self.config.qps,
                "tenants": self.config.tenants,
                "duration": self.config.duration,
                "topk": self.config.topk,
                "chunk_size": self.config.chunk_size,
                "warm_start": self.config.warm_start,
                "noisy_neighbor": self.config.noisy_neighbor,
                "base_url": self.config.base_url,
            },
            "timestamp": datetime.now(UTC).isoformat(),
            "overall_metrics": overall_metrics,
            "tenant_metrics": tenant_metrics,
            "variance_analysis": self._calculate_variance(tenant_metrics),
        }

    def _calculate_variance(self, tenant_metrics: dict[str, Any]) -> dict[str, Any]:
        """Calculate variance analysis across tenants."""
        p95_values = [m["p95_latency"] for m in tenant_metrics.values()]
        p99_values = [m["p99_latency"] for m in tenant_metrics.values()]

        return {
            "p95_variance": (statistics.variance(p95_values) if len(p95_values) > 1 else 0.0),
            "p99_variance": (statistics.variance(p99_values) if len(p99_values) > 1 else 0.0),
            "p95_cv": (
                statistics.stdev(p95_values) / statistics.mean(p95_values) if p95_values else 0.0
            ),
            "p99_cv": (
                statistics.stdev(p99_values) / statistics.mean(p99_values) if p99_values else 0.0
            ),
        }


async def main() -> None:
    """Execute the main benchmark entry point."""
    parser = argparse.ArgumentParser(description="Multi-tenant benchmark")
    parser.add_argument("--qps", type=int, default=50, help="Queries per second")
    parser.add_argument("--tenants", type=int, default=3, help="Number of tenants")
    parser.add_argument("--duration", type=int, default=300, help="Duration in seconds")
    parser.add_argument("--topk", type=int, default=10, help="Top-k parameter")
    parser.add_argument("--chunk", type=int, default=512, help="Chunk size")
    parser.add_argument("--warm", action="store_true", help="Enable warm start")
    parser.add_argument("--noisy-neighbor", action="store_true", help="Enable noisy neighbor")
    parser.add_argument("--output", default="artifacts/bench_multitenant.json", help="Output file")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL")

    args = parser.parse_args()

    # Create artifacts directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize benchmark
    config = BenchmarkConfig(
        qps=args.qps,
        tenants=args.tenants,
        duration=args.duration,
        topk=args.topk,
        chunk_size=args.chunk,
        warm_start=args.warm,
        noisy_neighbor=args.noisy_neighbor,
        base_url=args.base_url,
    )

    benchmark = MultiTenantBenchmark(config)
    benchmark.setup_tenants()

    # Run benchmark
    await benchmark.warm_up()
    await benchmark.run_benchmark()

    # Calculate and save results
    metrics = benchmark.calculate_metrics()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    log.info(f"Benchmark completed. Results saved to {output_path}")

    # Print summary
    overall = metrics["overall_metrics"]
    if overall:
        print("\nBenchmark Summary:")
        print(f"Total requests: {overall['total_requests']}")
        print(f"P95 latency: {overall['p95_latency']:.3f}s")
        print(f"P99 latency: {overall['p99_latency']:.3f}s")
        print(f"Mean latency: {overall['mean_latency']:.3f}s")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
