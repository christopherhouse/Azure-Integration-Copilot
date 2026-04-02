"""Tests for Cosmos DB telemetry enrichment (RU cost on OTel spans)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from shared.cosmos import _enrich_span_with_request_charge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline_response(headers: dict | None = None):
    """Build a minimal object that quacks like ``azure.core.pipeline.PipelineResponse``."""
    http_response = SimpleNamespace(headers=headers or {})
    return SimpleNamespace(http_response=http_response)


@pytest.fixture()
def _otel_provider():
    """Set up a minimal OTel TracerProvider for the test and restore afterwards."""
    provider = TracerProvider()
    original = trace.get_tracer_provider()
    trace.set_tracer_provider(provider)
    yield provider
    trace.set_tracer_provider(original)


# ---------------------------------------------------------------------------
# Tests — _enrich_span_with_request_charge
# ---------------------------------------------------------------------------


class TestEnrichSpanWithRequestCharge:
    """Unit tests for the response-hook that adds RU cost to OTel spans."""

    def test_sets_request_charge_attribute(self, _otel_provider):
        """When a recording span is active, the RU cost should be set as an attribute."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test-cosmos-op") as span:
            response = _make_pipeline_response({"x-ms-request-charge": "3.57"})
            _enrich_span_with_request_charge(response)

        # ReadableSpan exposes attributes after the span ends.
        assert span.attributes["db.cosmosdb.request_charge"] == 3.57

    def test_handles_integer_ru_value(self, _otel_provider):
        """RU values without decimals should still be stored as floats."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test-cosmos-op") as span:
            response = _make_pipeline_response({"x-ms-request-charge": "5"})
            _enrich_span_with_request_charge(response)

        assert span.attributes["db.cosmosdb.request_charge"] == 5.0

    def test_no_request_charge_header(self, _otel_provider):
        """When the header is missing, no attribute should be set."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test-cosmos-op") as span:
            response = _make_pipeline_response({})
            _enrich_span_with_request_charge(response)

        assert "db.cosmosdb.request_charge" not in (span.attributes or {})

    def test_non_numeric_header_value(self, _otel_provider):
        """A malformed header value should be silently ignored."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test-cosmos-op") as span:
            response = _make_pipeline_response({"x-ms-request-charge": "not-a-number"})
            _enrich_span_with_request_charge(response)

        assert "db.cosmosdb.request_charge" not in (span.attributes or {})

    def test_no_active_span(self, _otel_provider):
        """Should not raise when there is no active span."""
        response = _make_pipeline_response({"x-ms-request-charge": "2.0"})
        # No exception should be raised.
        _enrich_span_with_request_charge(response)

    def test_non_recording_span(self, _otel_provider):
        """Should not attempt to set attributes on a non-recording span."""
        response = _make_pipeline_response({"x-ms-request-charge": "2.0"})
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        with patch.object(trace, "get_current_span", return_value=mock_span):
            _enrich_span_with_request_charge(response)

        mock_span.set_attribute.assert_not_called()

    def test_none_response_object(self):
        """Should handle a completely broken response without raising."""
        _enrich_span_with_request_charge(None)

    def test_missing_http_response_attribute(self):
        """Should handle a response missing http_response without raising."""
        _enrich_span_with_request_charge(SimpleNamespace())
