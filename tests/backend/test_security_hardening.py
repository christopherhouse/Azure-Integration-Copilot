"""Security hardening tests — CORS validation, Content-Disposition sanitisation,
and streaming upload size enforcement.
"""

import io
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))


# ---------------------------------------------------------------------------
# CORS wildcard + credentials guard
# ---------------------------------------------------------------------------


class TestCorsWildcardGuard:
    """Startup must reject wildcard '*' in CORS_ALLOWED_ORIGINS."""

    def test_wildcard_cors_origin_raises_runtime_error(self):
        """Setting CORS_ALLOWED_ORIGINS='*' causes a RuntimeError at import time."""
        env = {
            "ENVIRONMENT": "test",
            "COSMOS_DB_ENDPOINT": "",
            "BLOB_STORAGE_ENDPOINT": "",
            "EVENT_GRID_NAMESPACE_ENDPOINT": "",
            "WEB_PUBSUB_ENDPOINT": "",
            "AZURE_CLIENT_ID": "",
            "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
            "SKIP_AUTH": "true",
            "CORS_ALLOWED_ORIGINS": "*",
        }
        # We need to force re-import of main to trigger the module-level guard.
        # Remove cached modules so the import path re-executes.
        modules_to_purge = [k for k in sys.modules if k.startswith("main") or k == "config"]
        saved = {k: sys.modules.pop(k) for k in modules_to_purge}
        try:
            with patch.dict(os.environ, env, clear=False):
                # Re-import config to pick up the new CORS_ALLOWED_ORIGINS
                import importlib

                import config as config_mod

                importlib.reload(config_mod)
                with pytest.raises(RuntimeError, match="wildcard origin"):
                    importlib.import_module("main")
        finally:
            # Restore previously cached modules
            for k, v in saved.items():
                sys.modules[k] = v
            # Reload config with original env so other tests are unaffected
            import importlib

            import config as config_mod

            importlib.reload(config_mod)

    def test_explicit_origins_do_not_raise(self):
        """Explicit origins like 'https://app.example.com' pass without error."""
        from config import settings

        original = settings.cors_allowed_origins
        settings.cors_allowed_origins = "https://app.example.com"
        try:
            origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
            assert "*" not in origins
        finally:
            settings.cors_allowed_origins = original


# ---------------------------------------------------------------------------
# Content-Disposition filename sanitisation
# ---------------------------------------------------------------------------


class TestContentDispositionSanitisation:
    """Verify that _sanitize_content_disposition prevents header injection."""

    def _sanitize(self, name: str) -> str:
        from domains.artifacts.router import _sanitize_content_disposition

        return _sanitize_content_disposition(name)

    def test_normal_ascii_filename(self):
        header = self._sanitize("workflow.json")
        assert 'filename="workflow.json"' in header
        assert "filename*=UTF-8''" in header
        assert header.startswith("attachment;")

    def test_strips_quotes_from_filename(self):
        header = self._sanitize('my"file".json')
        # Quotes must not appear in the ASCII fallback
        assert '"my"' not in header
        assert 'filename="myfile.json"' in header

    def test_strips_control_characters(self):
        header = self._sanitize("bad\r\nname\x00.json")
        # No CR/LF or null in ASCII fallback
        assert "\r" not in header.split(";")[1]
        assert "\n" not in header.split(";")[1]
        assert "\x00" not in header.split(";")[1]

    def test_strips_backslash(self):
        header = self._sanitize("path\\file.json")
        assert 'filename="pathfile.json"' in header

    def test_empty_after_sanitisation_uses_fallback(self):
        header = self._sanitize('"\x00"')
        assert 'filename="download"' in header

    def test_unicode_filename_encoded_in_filename_star(self):
        header = self._sanitize("日本語ファイル.json")
        # ASCII fallback has the unicode chars preserved (they are not in the
        # unsafe regex which targets control chars, quotes, backslashes)
        assert "filename*=UTF-8''" in header
        # The RFC 5987 portion must be percent-encoded
        assert "%E6%97%A5" in header  # 日 in UTF-8


# ---------------------------------------------------------------------------
# Streaming upload size enforcement
# ---------------------------------------------------------------------------


class TestStreamingUploadSizeEnforcement:
    """Upload must reject oversized files without reading the entire payload."""

    @pytest.mark.asyncio
    async def test_oversized_file_rejected_via_streaming(self):
        """ValueError raised when file exceeds tier limit during chunked read."""
        from domains.artifacts.service import ArtifactService
        from domains.tenants.models import Tenant, TenantStatus, TierDefinition, TierLimits, Usage

        tenant = Tenant(
            id="t-001",
            partitionKey="t-001",
            displayName="Test",
            ownerId="u-001",
            tierId="tier_free",
            status=TenantStatus.ACTIVE,
            usage=Usage(),
        )
        # 1 MB limit
        tier = TierDefinition(
            id="tier_free",
            name="Free",
            slug="free",
            limits=TierLimits(max_file_size_mb=1),
        )

        # Create a file mock that returns chunks exceeding 1 MB
        large_data = b"x" * (2 * 1024 * 1024)  # 2 MB

        file = MagicMock()
        chunk_size = 256 * 1024
        pos = 0

        async def mock_read(size=None):
            nonlocal pos
            if size is None:
                result = large_data[pos:]
                pos = len(large_data)
                return result
            result = large_data[pos : pos + size]
            pos += size
            return result

        file.read = mock_read
        file.seek = AsyncMock()
        file.filename = "bigfile.json"
        file.content_type = "application/json"

        svc = ArtifactService()
        with pytest.raises(ValueError, match="exceeds maximum"):
            with (
                patch("domains.artifacts.service.project_repository"),
                patch("domains.artifacts.service.artifact_repository"),
                patch("domains.artifacts.service.tenant_repository"),
                patch("domains.artifacts.service.blob_service"),
                patch("domains.artifacts.service.event_grid_publisher"),
            ):
                await svc.upload_artifact(
                    tenant=tenant,
                    tier=tier,
                    project_id="prj-001",
                    file=file,
                )

    @pytest.mark.asyncio
    async def test_small_file_accepted_via_streaming(self):
        """Files under the limit pass through streaming validation."""
        from domains.artifacts.service import ArtifactService
        from domains.tenants.models import Tenant, TenantStatus, TierDefinition, TierLimits, Usage

        tenant = Tenant(
            id="t-001",
            partitionKey="t-001",
            displayName="Test",
            ownerId="u-001",
            tierId="tier_free",
            status=TenantStatus.ACTIVE,
            usage=Usage(),
        )
        tier = TierDefinition(
            id="tier_free",
            name="Free",
            slug="free",
            limits=TierLimits(max_file_size_mb=1, max_artifacts_per_project=25),
        )

        small_data = b"small content"

        file = MagicMock()
        pos = 0

        async def mock_read(size=None):
            nonlocal pos
            if size is None:
                result = small_data[pos:]
                pos = len(small_data)
                return result
            result = small_data[pos : pos + size]
            pos += size
            return result

        file.read = mock_read
        file.seek = AsyncMock()
        file.filename = "workflow.json"
        file.content_type = "application/json"

        mock_project = MagicMock()
        mock_project.artifact_count = 0

        mock_artifact = MagicMock()
        mock_artifact.status = "uploading"

        svc = ArtifactService()
        with (
            patch("domains.artifacts.service.project_repository") as mock_proj,
            patch("domains.artifacts.service.artifact_repository") as mock_art_repo,
            patch("domains.artifacts.service.tenant_repository") as mock_tenant_repo,
            patch("domains.artifacts.service.blob_service") as mock_blob,
            patch("domains.artifacts.service.event_grid_publisher") as mock_eg,
            patch("domains.artifacts.service.detect_artifact_type", new_callable=AsyncMock, return_value="logic_app"),
            patch("domains.artifacts.service.compute_hash", new_callable=AsyncMock, return_value="abc123"),
        ):
            mock_proj.get_by_id = AsyncMock(return_value=mock_project)
            mock_proj.increment_artifact_count = AsyncMock()
            mock_art_repo.create = AsyncMock(return_value=mock_artifact)
            mock_art_repo.update = AsyncMock(return_value=mock_artifact)
            mock_blob.upload_blob = AsyncMock()
            mock_eg.publish_event = AsyncMock()
            mock_tenant_repo.increment_usage = AsyncMock()

            result = await svc.upload_artifact(
                tenant=tenant,
                tier=tier,
                project_id="prj-001",
                file=file,
            )
            assert result is not None
