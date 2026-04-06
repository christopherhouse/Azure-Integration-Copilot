"""OpenTelemetry metrics for security-relevant events (auth, quota).

Provides pre-configured counters and histograms that middleware components
increment as requests flow through the pipeline.  These metrics are
automatically exported to Azure Monitor when Application Insights is
configured; otherwise they remain available via the OTel SDK for local
inspection.
"""

from opentelemetry import metrics

_meter = metrics.get_meter("integrisight.security", version="0.1.0")

# ---------------------------------------------------------------------------
# Auth metrics
# ---------------------------------------------------------------------------

auth_attempts_counter = _meter.create_counter(
    name="auth.attempts",
    description="Total authentication attempts (success and failure)",
    unit="1",
)

# ---------------------------------------------------------------------------
# Quota metrics
# ---------------------------------------------------------------------------

quota_checks_counter = _meter.create_counter(
    name="quota.checks",
    description="Total quota evaluations (allowed and denied)",
    unit="1",
)

quota_usage_ratio_histogram = _meter.create_histogram(
    name="quota.usage_ratio",
    description="Quota usage ratio (current / maximum) at check time",
    unit="1",
)
