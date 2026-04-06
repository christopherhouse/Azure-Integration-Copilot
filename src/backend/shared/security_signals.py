"""Lightweight in-memory sliding-window anomaly detection for security signals.

Tracks event counts per source (tenant ID or IP) over configurable time
windows and emits structured log events when thresholds are exceeded.

Architecture note — per-instance vs. distributed tracking
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This tracker is **intentionally in-memory and per-instance**.  It serves as
a fast, zero-latency signal emitter (defense-in-depth), not a distributed
rate limiter.  Cross-instance aggregation is handled by two complementary
mechanisms that already exist in the pipeline:

1. **OTel metrics** (``shared/metrics.py``):  The ``auth.attempts`` and
   ``quota.checks`` counters are exported to Azure Monitor Application
   Insights, which aggregates them across *all* Container App replicas.
   Azure Monitor alert rules on these metrics provide cluster-wide
   anomaly detection with no additional infrastructure.

2. **Structured logs**:  Every ``security_anomaly`` log event is shipped
   to Application Insights via the OpenTelemetry log exporter.  KQL
   queries and alert rules can correlate events across instances.

Adding a shared store (e.g. Azure Cache for Redis) would provide true
distributed counting but introduces:
- ~1-2 ms network latency **per auth check** (currently 0 ms)
- A new PaaS dependency, cost, and operational surface
- A failure mode where cache unavailability could block auth entirely

The recommended upgrade path, if distributed real-time blocking is
needed, is to enable Azure Front Door WAF custom rate-limit rules at
the edge — which already sits in front of the Container Apps and can
enforce global rate limits without touching the application layer.
"""

import threading
import time
from collections import defaultdict

import structlog
from opentelemetry import trace

from config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration — overridable via environment variables
# ---------------------------------------------------------------------------

_AUTH_FAILURE_THRESHOLD: int = int(getattr(settings, "security_auth_failure_threshold", 10))
_AUTH_FAILURE_WINDOW_SECONDS: int = int(getattr(settings, "security_auth_failure_window_seconds", 300))
_QUOTA_BURST_THRESHOLD: int = int(getattr(settings, "security_quota_burst_threshold", 10))
_QUOTA_BURST_WINDOW_SECONDS: int = int(getattr(settings, "security_quota_burst_window_seconds", 300))


class SlidingWindowTracker:
    """Thread-safe sliding-window counter for a single anomaly type.

    Tracks timestamps of events per source key.  When the count within the
    window exceeds the threshold a structured log warning is emitted and
    an OTel span attribute is set.

    Stale entries are lazily pruned on each ``record`` call to bound memory.
    """

    def __init__(self, *, anomaly_type: str, threshold: int, window_seconds: int) -> None:
        self.anomaly_type = anomaly_type
        self.threshold = threshold
        self.window_seconds = window_seconds
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def record(self, source: str) -> bool:
        """Record an event for *source* and return ``True`` if the threshold was breached."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._events[source]
            # Prune expired entries
            self._events[source] = [t for t in timestamps if t > cutoff]
            self._events[source].append(now)
            count = len(self._events[source])

        if count >= self.threshold:
            logger.warning(
                "security_anomaly",
                anomaly_type=self.anomaly_type,
                anomaly_source=source,
                anomaly_count=count,
                anomaly_window_seconds=self.window_seconds,
            )
            span = trace.get_current_span()
            if span and span.is_recording():
                span.set_attribute("security.anomaly_detected", True)
                span.set_attribute("security.anomaly_type", self.anomaly_type)
            return True
        return False

    def count(self, source: str) -> int:
        """Return the current event count for *source* within the window (for testing)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            return len([t for t in self._events.get(source, []) if t > cutoff])


# ---------------------------------------------------------------------------
# Pre-configured trackers
# ---------------------------------------------------------------------------

auth_failure_tracker = SlidingWindowTracker(
    anomaly_type="auth_brute_force",
    threshold=_AUTH_FAILURE_THRESHOLD,
    window_seconds=_AUTH_FAILURE_WINDOW_SECONDS,
)

quota_burst_tracker = SlidingWindowTracker(
    anomaly_type="quota_burst",
    threshold=_QUOTA_BURST_THRESHOLD,
    window_seconds=_QUOTA_BURST_WINDOW_SECONDS,
)
