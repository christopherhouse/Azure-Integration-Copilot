"""Tests for Cosmos DB telemetry enrichment (RU cost on OTel spans)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from azure.core.pipeline.policies import DistributedTracingPolicy
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from shared.cosmos import (
    _enrich_span_with_request_charge,
    _patch_distributed_tracing_for_ru_cost,
)

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


@pytest.fixture(autouse=True)
def _reset_patch(monkeypatch):
    """Reset the module-level patch guard so each test can apply it fresh."""
    import shared.cosmos as cosmos_mod

    monkeypatch.setattr(cosmos_mod, "_ru_patch_applied", False)


# ---------------------------------------------------------------------------
# Tests — _enrich_span_with_request_charge
# ---------------------------------------------------------------------------


class TestEnrichSpanWithRequestCharge:
    """Unit tests for the function that sets RU cost on a span."""

    def test_sets_request_charge_attribute(self, _otel_provider):
        """When a recording span is provided, the RU cost should be set as an attribute."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test-cosmos-op") as span:
            response = _make_pipeline_response({"x-ms-request-charge": "3.57"})
            _enrich_span_with_request_charge(span, response)

        assert span.attributes["db.cosmosdb.request_charge"] == 3.57

    def test_handles_integer_ru_value(self, _otel_provider):
        """RU values without decimals should still be stored as floats."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test-cosmos-op") as span:
            response = _make_pipeline_response({"x-ms-request-charge": "5"})
            _enrich_span_with_request_charge(span, response)

        assert span.attributes["db.cosmosdb.request_charge"] == 5.0

    def test_no_request_charge_header(self, _otel_provider):
        """When the header is missing, no attribute should be set."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test-cosmos-op") as span:
            response = _make_pipeline_response({})
            _enrich_span_with_request_charge(span, response)

        assert "db.cosmosdb.request_charge" not in (span.attributes or {})

    def test_non_numeric_header_value(self, _otel_provider):
        """A malformed header value should be silently ignored."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test-cosmos-op") as span:
            response = _make_pipeline_response({"x-ms-request-charge": "not-a-number"})
            _enrich_span_with_request_charge(span, response)

        assert "db.cosmosdb.request_charge" not in (span.attributes or {})

    def test_non_recording_span(self):
        """Should not attempt to set attributes on a non-recording span."""
        response = _make_pipeline_response({"x-ms-request-charge": "2.0"})
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        _enrich_span_with_request_charge(mock_span, response)
        mock_span.set_attribute.assert_not_called()

    def test_none_span(self):
        """Should handle a None span without raising."""
        response = _make_pipeline_response({"x-ms-request-charge": "2.0"})
        _enrich_span_with_request_charge(None, response)

    def test_none_response_object(self):
        """Should handle a completely broken response without raising."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        _enrich_span_with_request_charge(mock_span, None)

    def test_missing_http_response_attribute(self):
        """Should handle a response missing http_response without raising."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        _enrich_span_with_request_charge(mock_span, SimpleNamespace())


# ---------------------------------------------------------------------------
# Tests — _patch_distributed_tracing_for_ru_cost
# ---------------------------------------------------------------------------


class TestPatchDistributedTracingForRuCost:
    """Tests for the monkey-patch that enriches DTP with RU cost."""

    @pytest.fixture(autouse=True)
    def _save_and_restore_dtp(self):
        """Save the original on_response and restore it after each test."""
        original = DistributedTracingPolicy.on_response
        yield
        DistributedTracingPolicy.on_response = original

    def test_patch_replaces_on_response(self):
        """After patching, DTP.on_response should be the wrapped version."""
        original = DistributedTracingPolicy.on_response
        _patch_distributed_tracing_for_ru_cost()
        assert DistributedTracingPolicy.on_response is not original

    def test_patch_is_idempotent(self):
        """Calling the patch twice should only wrap once."""
        _patch_distributed_tracing_for_ru_cost()
        first_patched = DistributedTracingPolicy.on_response
        # Re-enable the guard so a second call can test idempotency
        import shared.cosmos as cosmos_mod

        cosmos_mod._ru_patch_applied = True
        _patch_distributed_tracing_for_ru_cost()
        assert DistributedTracingPolicy.on_response is first_patched

    def test_patched_on_response_sets_ru_before_ending_span(self, _otel_provider):
        """The patched on_response should set RU charge while the span is recording."""
        # Record whether the original on_response was called and if the span
        # was still recording at that point.
        call_log: list[bool] = []

        def tracking_original(self, request, response):
            span = request.context.get(DistributedTracingPolicy.TRACING_CONTEXT)
            if span:
                # By this point our wrapper should already have set the attr.
                call_log.append(True)
                span.end()  # simulate what the real on_response does

        # Temporarily install the tracking original, then apply our patch on top.
        DistributedTracingPolicy.on_response = tracking_original
        _patch_distributed_tracing_for_ru_cost()

        tracer = trace.get_tracer(__name__)
        span = tracer.start_span("test-cosmos-op")

        mock_request = MagicMock()
        mock_request.context = {DistributedTracingPolicy.TRACING_CONTEXT: span}

        mock_response = _make_pipeline_response({"x-ms-request-charge": "7.42"})

        policy = DistributedTracingPolicy()
        DistributedTracingPolicy.on_response(policy, mock_request, mock_response)

        # Original was called
        assert call_log == [True]
        # RU charge was set while span was still recording
        assert span.attributes.get("db.cosmosdb.request_charge") == 7.42

    def test_patched_on_response_calls_original(self):
        """The patched on_response must still call the original method."""
        original_called = []

        def mock_original(self, request, response):
            original_called.append(True)

        DistributedTracingPolicy.on_response = mock_original
        _patch_distributed_tracing_for_ru_cost()

        policy = DistributedTracingPolicy()
        mock_request = MagicMock()
        mock_request.context = {}
        mock_response = _make_pipeline_response({})

        DistributedTracingPolicy.on_response(policy, mock_request, mock_response)
        assert original_called == [True]

    def test_patched_on_response_no_crash_without_tracing_context(self):
        """Patched on_response should not crash when TRACING_CONTEXT is missing."""
        def noop_original(self, request, response):
            pass

        DistributedTracingPolicy.on_response = noop_original
        _patch_distributed_tracing_for_ru_cost()

        policy = DistributedTracingPolicy()
        mock_request = MagicMock()
        mock_request.context = {}
        mock_response = _make_pipeline_response({"x-ms-request-charge": "3.0"})

        # Should not raise even though no span is in context
        DistributedTracingPolicy.on_response(policy, mock_request, mock_response)

    def test_patched_on_response_harmless_for_non_cosmos(self, _otel_provider):
        """For non-Cosmos responses (no x-ms-request-charge), enrichment is a no-op."""
        def noop_original(self, request, response):
            pass

        DistributedTracingPolicy.on_response = noop_original
        _patch_distributed_tracing_for_ru_cost()

        tracer = trace.get_tracer(__name__)
        span = tracer.start_span("test-non-cosmos-op")

        mock_request = MagicMock()
        mock_request.context = {DistributedTracingPolicy.TRACING_CONTEXT: span}

        mock_response = _make_pipeline_response({})  # no RU header

        policy = DistributedTracingPolicy()
        DistributedTracingPolicy.on_response(policy, mock_request, mock_response)

        assert "db.cosmosdb.request_charge" not in (span.attributes or {})
