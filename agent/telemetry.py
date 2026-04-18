import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

_tracer = None


def init_telemetry() -> trace.Tracer:
    """Initialise OpenTelemetry tracing. Exports to console by default."""
    global _tracer
    if _tracer:
        return _tracer

    resource = Resource.create({"service.name": "guardrail-enforcement-agent"})
    provider = TracerProvider(resource=resource)

    # Console exporter for visibility — replace with OTLP exporter for production
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    # Optional: OTLP exporter if endpoint is configured
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
        except ImportError:
            pass

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("guardrail-agent")
    return _tracer


def trace_scan(scan_id: str, resources_scanned: int, violations_found: int, pr_url: str | None):
    """Emit a trace span for a complete enforcement scan."""
    tracer = init_telemetry()
    with tracer.start_as_current_span("enforcement-scan") as span:
        span.set_attribute("agent.scan_id", scan_id)
        span.set_attribute("agent.resources_scanned", resources_scanned)
        span.set_attribute("agent.violations_found", violations_found)
        span.set_attribute("agent.pr_created", pr_url is not None)
        span.set_attribute("agent.pr_url", pr_url or "")
