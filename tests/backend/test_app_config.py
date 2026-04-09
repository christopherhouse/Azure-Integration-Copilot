"""Tests for shared.app_config.AppConfigService."""

from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_test_env = {
    "ENVIRONMENT": "test",
    "COSMOS_DB_ENDPOINT": "",
    "BLOB_STORAGE_ENDPOINT": "",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "",
    "WEB_PUBSUB_ENDPOINT": "",
    "AZURE_CLIENT_ID": "",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
    "SKIP_AUTH": "true",
    "APP_CONFIG_ENDPOINT": "https://appcs-test.azconfig.io",
}

with patch.dict(os.environ, _test_env):
    from shared.app_config import AppConfigService  # noqa: E402
    import config as _config  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kv(key: str, value: str) -> MagicMock:
    kv = MagicMock()
    kv.key = key
    kv.value = value
    return kv


async def _async_iter(items):
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# ensure_loaded — endpoint configured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_loaded_populates_cache():
    """ensure_loaded fetches key-values and populates the cache."""
    svc = AppConfigService()
    mock_client = AsyncMock()
    mock_client.list_configuration_settings = MagicMock(
        return_value=_async_iter([_make_kv("feature.enabled", "true"), _make_kv("retry.count", "3")])
    )

    with (
        patch.object(_config.settings, "app_config_endpoint", "https://appcs-test.azconfig.io"),
        patch.object(svc, "_get_client", new_callable=AsyncMock, return_value=mock_client),
    ):
        await svc.ensure_loaded()

    assert svc.get("feature.enabled") == "true"
    assert svc.get("retry.count") == "3"
    assert svc._loaded is True


@pytest.mark.asyncio
async def test_ensure_loaded_only_loads_once():
    """ensure_loaded is idempotent — network call happens exactly once."""
    svc = AppConfigService()
    call_count = 0

    async def _fake_load():
        nonlocal call_count
        call_count += 1
        svc._cache = {"k": "v"}
        svc._loaded = True
        svc._last_refresh = time.monotonic()

    with (
        patch.object(_config.settings, "app_config_endpoint", "https://appcs-test.azconfig.io"),
        patch.object(svc, "_load", side_effect=_fake_load),
    ):
        await svc.ensure_loaded()
        await svc.ensure_loaded()

    assert call_count == 1


@pytest.mark.asyncio
async def test_ensure_loaded_handles_exception_gracefully():
    """ensure_loaded does not raise even when the SDK call fails."""
    svc = AppConfigService()
    mock_client = AsyncMock()
    mock_client.list_configuration_settings = MagicMock(side_effect=Exception("network error"))

    with (
        patch.object(_config.settings, "app_config_endpoint", "https://appcs-test.azconfig.io"),
        patch.object(svc, "_get_client", new_callable=AsyncMock, return_value=mock_client),
    ):
        await svc.ensure_loaded()  # must not raise

    assert svc._loaded is False


# ---------------------------------------------------------------------------
# ensure_loaded — no endpoint configured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_loaded_no_op_when_endpoint_not_set():
    """ensure_loaded skips the network call when APP_CONFIG_ENDPOINT is empty."""
    svc = AppConfigService()
    with (
        patch.object(_config.settings, "app_config_endpoint", ""),
        patch.object(svc, "_load", new_callable=AsyncMock) as mock_load,
    ):
        await svc.ensure_loaded()
        mock_load.assert_not_called()


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_cached_value():
    svc = AppConfigService()
    svc._cache = {"mykey": "myvalue"}
    svc._loaded = True
    assert svc.get("mykey") == "myvalue"


@pytest.mark.asyncio
async def test_get_returns_default_for_missing_key():
    svc = AppConfigService()
    svc._loaded = True
    assert svc.get("missing") is None
    assert svc.get("missing", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# on_config_changed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_config_changed_refreshes_cache():
    """on_config_changed triggers a reload when interval has passed."""
    svc = AppConfigService()
    svc._loaded = True
    svc._last_refresh = 0.0  # force elapsed > _MIN_REFRESH_INTERVAL

    refreshed = False

    async def _fake_load():
        nonlocal refreshed
        refreshed = True
        svc._cache = {"new": "value"}
        svc._last_refresh = time.monotonic()

    with (
        patch.object(_config.settings, "app_config_endpoint", "https://appcs-test.azconfig.io"),
        patch.object(svc, "_load", side_effect=_fake_load),
    ):
        await svc.on_config_changed()

    assert refreshed is True
    assert svc.get("new") == "value"


@pytest.mark.asyncio
async def test_on_config_changed_skips_when_too_soon():
    """on_config_changed respects the minimum refresh interval."""
    svc = AppConfigService()
    svc._loaded = True
    svc._last_refresh = time.monotonic()  # just refreshed

    with (
        patch.object(_config.settings, "app_config_endpoint", "https://appcs-test.azconfig.io"),
        patch.object(svc, "_load", new_callable=AsyncMock) as mock_load,
    ):
        await svc.on_config_changed()
        mock_load.assert_not_called()


@pytest.mark.asyncio
async def test_on_config_changed_no_op_when_endpoint_not_set():
    svc = AppConfigService()
    with (
        patch.object(_config.settings, "app_config_endpoint", ""),
        patch.object(svc, "_load", new_callable=AsyncMock) as mock_load,
    ):
        await svc.on_config_changed()
        mock_load.assert_not_called()


@pytest.mark.asyncio
async def test_on_config_changed_handles_exception_gracefully():
    """on_config_changed does not propagate exceptions from _load."""
    svc = AppConfigService()
    svc._last_refresh = 0.0

    with (
        patch.object(_config.settings, "app_config_endpoint", "https://appcs-test.azconfig.io"),
        patch.object(svc, "_load", new_callable=AsyncMock, side_effect=Exception("SDK error")),
    ):
        await svc.on_config_changed()  # must not raise


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_releases_client():
    """close() closes the underlying SDK client and clears the reference."""
    svc = AppConfigService()
    mock_client = AsyncMock()
    svc._client = mock_client
    svc._loaded = True

    await svc.close()

    mock_client.close.assert_awaited_once()
    assert svc._client is None
    assert svc._loaded is False


@pytest.mark.asyncio
async def test_close_is_safe_when_never_initialized():
    """close() is a no-op when the client was never created."""
    svc = AppConfigService()
    await svc.close()  # must not raise

