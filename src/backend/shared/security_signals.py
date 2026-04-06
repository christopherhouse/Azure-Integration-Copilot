"""Lightweight in-memory sliding-window anomaly detection for security signals.

Tracks event counts per source (tenant ID or IP) over configurable time
windows and emits structured log events when thresholds are exceeded.
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
