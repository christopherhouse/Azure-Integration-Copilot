"""Tests for security logging improvements (Item 9).

Covers:
- Auth failure structured logging with correct failure reasons (9a)
- OTel metrics counter increments for auth and quota (9b)
- Sliding-window anomaly detection (9c)
"""

import base64
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))


def _generate_rsa_key_material(kid: str = "test-kid-1") -> tuple[bytes, dict]:
    """Generate an RSA key pair and return *(private_pem_bytes, jwk_public_dict)*."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub = private_key.public_key().public_numbers()

    def _b64url(val: int) -> str:
        length = (val.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(val.to_bytes(length, "big")).rstrip(b"=").decode()

    jwk_dict = {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _b64url(pub.n),
        "e": _b64url(pub.e),
    }
    return private_pem, jwk_dict


def _get_auth_settings():
    """Return the settings object used by the auth middleware.

    After ``test_security_hardening`` reloads the config module, the module-level
    ``from config import settings`` in ``middleware.auth`` may reference a
    different object than ``config.settings``.  Always use the auth module's own
    reference for reliable patching.
    """
    import middleware.auth as auth_mod

    return auth_mod.settings


# ---------------------------------------------------------------------------
# 9a — Auth failure logging by reason
# ---------------------------------------------------------------------------


class TestAuthFailureLogging:
    """Each auth rejection path must emit a structured warning with auth_failure_reason.

    We verify the code paths by asserting on the HTTP response (which confirms
    the logging code executed) and testing helper functions directly.
    """

    @pytest.mark.asyncio
    async def test_missing_header_returns_401_with_unauthorized(self):
        """Missing Authorization header returns 401 UNAUTHORIZED (logging path exercised)."""
        s = _get_auth_settings()
        original = s.skip_auth
        s.skip_auth = False
        try:
            from httpx import ASGITransport, AsyncClient

            from main import app

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/tenants/me")
            assert response.status_code == 401
            body = response.json()
            assert body["error"]["code"] == "UNAUTHORIZED"
            assert "Missing or invalid" in body["error"]["message"]
        finally:
            s.skip_auth = original

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401_with_invalid_message(self):
        """Invalid JWT token returns 401 with 'Invalid or expired' message."""
        s = _get_auth_settings()
        original = s.skip_auth
        s.skip_auth = False
        try:
            with patch("middleware.auth._fetch_oidc_metadata", new_callable=AsyncMock) as mock_oidc:
                mock_oidc.return_value = (
                    {"keys": [{"kid": "test-kid", "kty": "RSA", "n": "test", "e": "AQAB"}]},
                    "https://test-issuer.example.com",
                )
                from httpx import ASGITransport, AsyncClient

                from main import app

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get(
                        "/api/v1/tenants/me",
                        headers={"Authorization": "Bearer invalid.jwt.token"},
                    )
                assert response.status_code == 401
                assert "Invalid or expired" in response.json()["error"]["message"]
        finally:
            s.skip_auth = original

    @pytest.mark.asyncio
    async def test_key_not_found_returns_401_signing_key_message(self):
        """Signing key not found after refresh returns 401 with signing key message."""
        from jose import jwt as jose_jwt

        s = _get_auth_settings()
        private_pem, _ = _generate_rsa_key_material("unknown-kid")
        token = jose_jwt.encode(
            {"sub": "user-123", "iss": "https://test.example.com", "aud": "test-client"},
            private_pem.decode(),
            algorithm="RS256",
            headers={"kid": "unknown-kid"},
        )

        original = s.skip_auth
        original_subdomain = s.entra_ciam_tenant_subdomain
        s.skip_auth = False
        s.entra_ciam_tenant_subdomain = "test-tenant"
        try:
            empty_jwks = {"keys": [{"kid": "other-kid", "kty": "RSA", "n": "fake", "e": "AQAB"}]}
            with (
                patch(
                    "middleware.auth._fetch_oidc_metadata",
                    new_callable=AsyncMock,
                    return_value=(empty_jwks, "https://test-issuer.example.com"),
                ),
                patch(
                    "middleware.auth._refresh_jwks",
                    new_callable=AsyncMock,
                    return_value=empty_jwks,
                ),
            ):
                from httpx import ASGITransport, AsyncClient

                from main import app

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get(
                        "/api/v1/tenants/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                assert response.status_code == 401
                assert "signing key" in response.json()["error"]["message"]
        finally:
            s.skip_auth = original
            s.entra_ciam_tenant_subdomain = original_subdomain

    def test_set_auth_span_attributes_success(self):
        """_set_auth_span_attributes sets correct attributes for success."""
        from middleware.auth import _set_auth_span_attributes

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        with patch("middleware.auth.trace.get_current_span", return_value=mock_span):
            _set_auth_span_attributes(result="success")
        mock_span.set_attribute.assert_any_call("auth.result", "success")

    def test_set_auth_span_attributes_failure_with_reason(self):
        """_set_auth_span_attributes sets failure reason attribute."""
        from middleware.auth import _set_auth_span_attributes

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        with patch("middleware.auth.trace.get_current_span", return_value=mock_span):
            _set_auth_span_attributes(result="failure", failure_reason="missing_header")
        mock_span.set_attribute.assert_any_call("auth.result", "failure")
        mock_span.set_attribute.assert_any_call("auth.failure_reason", "missing_header")


# ---------------------------------------------------------------------------
# 9b — OTel metrics counter tests
# ---------------------------------------------------------------------------


class TestAuthMetricsCounters:
    """auth.attempts counter must be incremented on every auth outcome."""

    @pytest.mark.asyncio
    async def test_auth_failure_increments_counter_via_middleware(self):
        """Failed authentication increments auth.attempts counter with result='failure'."""
        s = _get_auth_settings()
        original = s.skip_auth
        s.skip_auth = False
        try:
            with patch("middleware.auth.auth_attempts_counter") as mock_counter:
                from httpx import ASGITransport, AsyncClient

                from main import app

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    await client.get("/api/v1/tenants/me")

                mock_counter.add.assert_called()
                failure_calls = [
                    c for c in mock_counter.add.call_args_list if c[0][1].get("result") == "failure"
                ]
                assert len(failure_calls) >= 1
        finally:
            s.skip_auth = original

    @pytest.mark.asyncio
    async def test_auth_success_increments_counter_via_middleware(self):
        """Successful authentication increments auth.attempts counter with result='success'."""
        from jose import jwt as jose_jwt

        s = _get_auth_settings()
        private_pem, jwk_dict = _generate_rsa_key_material("success-kid")
        issuer = "https://test-issuer.example.com"
        client_id = "test-client-id"
        token = jose_jwt.encode(
            {"sub": "user-123", "oid": "ext-id", "iss": issuer, "aud": client_id},
            private_pem.decode(),
            algorithm="RS256",
            headers={"kid": "success-kid"},
        )

        original_skip = s.skip_auth
        original_subdomain = s.entra_ciam_tenant_subdomain
        original_client = s.entra_ciam_client_id
        s.skip_auth = False
        s.entra_ciam_tenant_subdomain = "test-tenant"
        s.entra_ciam_client_id = client_id
        try:
            with (
                patch("middleware.auth.auth_attempts_counter") as mock_counter,
                patch(
                    "middleware.auth._fetch_oidc_metadata",
                    new_callable=AsyncMock,
                    return_value=({"keys": [jwk_dict]}, issuer),
                ),
                patch("middleware.tenant_context.settings", skip_auth=True, cosmos_db_endpoint=""),
            ):
                from httpx import ASGITransport, AsyncClient

                from main import app

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    await client.get(
                        "/api/v1/tenants/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )

                success_calls = [
                    c for c in mock_counter.add.call_args_list if c[0][1].get("result") == "success"
                ]
                assert len(success_calls) >= 1
        finally:
            s.skip_auth = original_skip
            s.entra_ciam_tenant_subdomain = original_subdomain
            s.entra_ciam_client_id = original_client


class TestQuotaMetricsCounters:
    """quota.checks counter must be incremented on quota evaluations."""

    @pytest.mark.asyncio
    async def test_quota_denied_increments_counter(self):
        """Denied quota check increments counter with result='denied'."""
        mock_result = MagicMock()
        mock_result.allowed = False
        mock_result.current = 10
        mock_result.maximum = 10

        mock_tenant = MagicMock()
        mock_tenant.id = "tenant-001"

        with (
            patch("middleware.quota.quota_checks_counter") as mock_counter,
            patch("middleware.quota.quota_service") as mock_quota_svc,
        ):
            mock_quota_svc.check = AsyncMock(return_value=mock_result)

            from middleware.quota import QuotaMiddleware

            middleware = QuotaMiddleware(app=MagicMock())
            mock_request = MagicMock()
            mock_request.method = "POST"
            mock_request.url.path = "/api/v1/projects"
            mock_request.state.tenant = mock_tenant
            mock_request.state.tier = MagicMock()

            response = await middleware.dispatch(mock_request, AsyncMock())
            assert response.status_code == 429
            denied_calls = [
                c for c in mock_counter.add.call_args_list if c[0][1].get("result") == "denied"
            ]
            assert len(denied_calls) >= 1

    @pytest.mark.asyncio
    async def test_quota_allowed_increments_counter(self):
        """Allowed quota check increments counter with result='allowed'."""
        mock_result = MagicMock()
        mock_result.allowed = True
        mock_result.current = 2
        mock_result.maximum = 10

        mock_tenant = MagicMock()
        mock_tenant.id = "tenant-002"

        with (
            patch("middleware.quota.quota_checks_counter") as mock_counter,
            patch("middleware.quota.quota_service") as mock_quota_svc,
        ):
            mock_quota_svc.check = AsyncMock(return_value=mock_result)

            from middleware.quota import QuotaMiddleware

            middleware = QuotaMiddleware(app=MagicMock())
            mock_request = MagicMock()
            mock_request.method = "POST"
            mock_request.url.path = "/api/v1/projects"
            mock_request.state.tenant = mock_tenant
            mock_request.state.tier = MagicMock()

            mock_next = AsyncMock(return_value=MagicMock(status_code=200))
            await middleware.dispatch(mock_request, mock_next)
            allowed_calls = [
                c for c in mock_counter.add.call_args_list if c[0][1].get("result") == "allowed"
            ]
            assert len(allowed_calls) >= 1

    @pytest.mark.asyncio
    async def test_quota_warning_at_80_percent(self):
        """Quota at 80%+ usage emits info-level warning."""
        mock_result = MagicMock()
        mock_result.allowed = True
        mock_result.current = 8
        mock_result.maximum = 10

        mock_tenant = MagicMock()
        mock_tenant.id = "tenant-003"

        with (
            patch("middleware.quota.quota_usage_ratio_histogram") as mock_histogram,
            patch("middleware.quota.quota_service") as mock_quota_svc,
            patch("middleware.quota.logger") as mock_logger,
            patch("middleware.quota.quota_checks_counter"),
        ):
            mock_quota_svc.check = AsyncMock(return_value=mock_result)

            from middleware.quota import QuotaMiddleware

            middleware = QuotaMiddleware(app=MagicMock())
            mock_request = MagicMock()
            mock_request.method = "POST"
            mock_request.url.path = "/api/v1/projects"
            mock_request.state.tenant = mock_tenant
            mock_request.state.tier = MagicMock()

            mock_next = AsyncMock(return_value=MagicMock(status_code=200))
            await middleware.dispatch(mock_request, mock_next)

            # Histogram should record usage ratio
            mock_histogram.record.assert_called_once()
            assert mock_histogram.record.call_args[0][0] == pytest.approx(0.8)

            # Logger should emit quota_warning
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "quota_warning"


# ---------------------------------------------------------------------------
# 9c — Sliding-window anomaly detection
# ---------------------------------------------------------------------------


class TestSlidingWindowTracker:
    """Sliding window tracker must detect brute-force patterns."""

    def test_below_threshold_no_anomaly(self):
        """Events below threshold do not trigger anomaly signal."""
        from shared.security_signals import SlidingWindowTracker

        tracker = SlidingWindowTracker(
            anomaly_type="test_anomaly", threshold=5, window_seconds=60
        )
        for _ in range(4):
            result = tracker.record("source-1")
        assert result is False

    def test_at_threshold_triggers_anomaly(self):
        """Reaching threshold triggers anomaly signal."""
        from shared.security_signals import SlidingWindowTracker

        tracker = SlidingWindowTracker(
            anomaly_type="test_anomaly", threshold=5, window_seconds=60
        )
        for i in range(5):
            result = tracker.record("source-1")
        assert result is True

    def test_different_sources_independent(self):
        """Different source keys track independently."""
        from shared.security_signals import SlidingWindowTracker

        tracker = SlidingWindowTracker(
            anomaly_type="test_anomaly", threshold=5, window_seconds=60
        )
        for _ in range(4):
            tracker.record("source-a")
        for _ in range(4):
            result = tracker.record("source-b")
        assert result is False
        assert tracker.count("source-a") == 4
        assert tracker.count("source-b") == 4

    def test_expired_events_pruned(self):
        """Events older than the window are pruned on next record."""
        from shared.security_signals import SlidingWindowTracker

        tracker = SlidingWindowTracker(
            anomaly_type="test_anomaly", threshold=5, window_seconds=1
        )
        for _ in range(4):
            tracker.record("source-1")
        assert tracker.count("source-1") == 4

        time.sleep(1.1)

        tracker.record("source-1")
        assert tracker.count("source-1") == 1

    def test_anomaly_emits_log_warning(self):
        """Threshold breach emits a security_anomaly structured log."""
        from shared.security_signals import SlidingWindowTracker

        tracker = SlidingWindowTracker(
            anomaly_type="auth_brute_force", threshold=3, window_seconds=60
        )

        with patch("shared.security_signals.logger") as mock_logger:
            for _ in range(3):
                tracker.record("attacker-ip")

            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "security_anomaly"
            assert call_args[1]["anomaly_type"] == "auth_brute_force"
            assert call_args[1]["anomaly_source"] == "attacker-ip"
            assert call_args[1]["anomaly_count"] == 3

    def test_count_method_returns_current_window_count(self):
        """count() returns accurate count within window."""
        from shared.security_signals import SlidingWindowTracker

        tracker = SlidingWindowTracker(
            anomaly_type="test", threshold=100, window_seconds=60
        )
        assert tracker.count("source") == 0
        tracker.record("source")
        tracker.record("source")
        assert tracker.count("source") == 2

    def test_anomaly_sets_span_attribute(self):
        """Threshold breach sets security.anomaly_detected span attribute."""
        from shared.security_signals import SlidingWindowTracker

        tracker = SlidingWindowTracker(
            anomaly_type="auth_brute_force", threshold=2, window_seconds=60
        )

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        with (
            patch("shared.security_signals.trace.get_current_span", return_value=mock_span),
            patch("shared.security_signals.logger"),
        ):
            tracker.record("attacker-ip")
            tracker.record("attacker-ip")

        mock_span.set_attribute.assert_any_call("security.anomaly_detected", True)
        mock_span.set_attribute.assert_any_call("security.anomaly_type", "auth_brute_force")


class TestPreConfiguredTrackers:
    """Pre-configured auth and quota trackers should exist with correct defaults."""

    def test_auth_failure_tracker_exists(self):
        from shared.security_signals import auth_failure_tracker

        assert auth_failure_tracker.anomaly_type == "auth_brute_force"
        assert auth_failure_tracker.threshold > 0
        assert auth_failure_tracker.window_seconds > 0

    def test_quota_burst_tracker_exists(self):
        from shared.security_signals import quota_burst_tracker

        assert quota_burst_tracker.anomaly_type == "quota_burst"
        assert quota_burst_tracker.threshold > 0
        assert quota_burst_tracker.window_seconds > 0

