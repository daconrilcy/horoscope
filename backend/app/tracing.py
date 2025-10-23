"""Configuration du tracing OpenTelemetry pour l'observabilité.

Ce module configure le tracing distribué avec OpenTelemetry pour exporter les traces vers un
endpoint OTLP configuré via les variables d'environnement.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from backend.core.container import container


def setup_tracing():
    """Configure le tracing OpenTelemetry pour l'observabilité.

    Initialise le provider de tracing et configure l'exporteur OTLP si l'endpoint est configuré dans
    les paramètres.
    """
    if not getattr(container.settings, "OTLP_ENDPOINT", None):
        return

    provider = TracerProvider()
    processor = BatchSpanProcessor(
        OTLPSpanExporter(endpoint=container.settings.OTLP_ENDPOINT, insecure=True)
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
