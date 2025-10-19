

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from backend.core.container import container


def setup_tracing():
    return
    provider = TracerProvider()
    processor = BatchSpanProcessor(
        OTLPSpanExporter(endpoint=container.settings.OTLP_ENDPOINT, insecure=True)
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
