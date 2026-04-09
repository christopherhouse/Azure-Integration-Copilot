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
# get_by_prefix
# ---------------------------------------------------------------------------


def test_get_by_prefix_returns_matching_keys():
    svc = AppConfigService()
    svc._cache = {
        "feature.new-ui": "true",
        "feature.dark-mode": "false",
        "other.setting": "value",
    }
    result = svc.get_by_prefix("feature.")
    assert result == {"feature.new-ui": "true", "feature.dark-mode": "false"}


def test_get_by_prefix_returns_empty_when_no_match():
    svc = AppConfigService()
    svc._cache = {"other.setting": "value"}
    assert svc.get_by_prefix("feature.") == {}


def test_get_by_prefix_returns_empty_when_cache_is_empty():
    svc = AppConfigService()
    assert svc.get_by_prefix("feature.") == {}


def test_get_by_prefix_does_not_strip_prefix():
    """Keys in the returned dict retain their original names."""
    svc = AppConfigService()
    svc._cache = {"feature.my-flag": "true"}
    result = svc.get_by_prefix("feature.")
    assert "feature.my-flag" in result


# ---------------------------------------------------------------------------
# get_feature_flags
# ---------------------------------------------------------------------------


def test_get_feature_flags_returns_enabled_flags():
    """Feature flags with enabled=true are returned as True."""
    svc = AppConfigService()
    svc._cache = {
        '.appconfig.featureflag/flag-a': '{"id":"flag-a","enabled":true,"conditions":{}}',
        '.appconfig.featureflag/flag-b': '{"id":"flag-b","enabled":false,"conditions":{}}',
        'other.setting': 'value',
    }
    result = svc.get_feature_flags()
    assert result == {"flag-a": True, "flag-b": False}


def test_get_feature_flags_ignores_non_feature_keys():
    """Only keys with the .appconfig.featureflag/ prefix are returned."""
    svc = AppConfigService()
    svc._cache = {
        '.appconfig.featureflag/my-flag': '{"id":"my-flag","enabled":true}',
        'feature.old-style': 'true',
        'some.config': 'value',
    }
    result = svc.get_feature_flags()
    assert result == {"my-flag": True}


def test_get_feature_flags_returns_empty_when_no_flags():
    svc = AppConfigService()
    svc._cache = {"other.setting": "value"}
    assert svc.get_feature_flags() == {}


def test_get_feature_flags_returns_empty_when_cache_is_empty():
    svc = AppConfigService()
    assert svc.get_feature_flags() == {}


def test_get_feature_flags_handles_malformed_json():
    """Malformed JSON values are treated as disabled."""
    svc = AppConfigService()
    svc._cache = {
        '.appconfig.featureflag/bad-json': 'not-json',
        '.appconfig.featureflag/good': '{"id":"good","enabled":true}',
    }
    result = svc.get_feature_flags()
    assert result["bad-json"] is False
    assert result["good"] is True


def test_get_feature_flags_handles_missing_enabled_field():
    """JSON values without an 'enabled' field are treated as disabled."""
    svc = AppConfigService()
    svc._cache = {
        '.appconfig.featureflag/no-enabled': '{"id":"no-enabled","conditions":{}}',
    }
    result = svc.get_feature_flags()
    assert result["no-enabled"] is False


# ---------------------------------------------------------------------------
# _load with FeatureFlagConfigurationSetting
# ---------------------------------------------------------------------------


def _make_feature_flag_kv(feature_id: str, enabled: bool):
    """Create a mock FeatureFlagConfigurationSetting.

    The returned mock quacks like the SDK's FeatureFlagConfigurationSetting
    so that ``isinstance(kv, FeatureFlagConfigurationSetting)`` returns True.
    """
    from azure.appconfiguration import FeatureFlagConfigurationSetting

    kv = MagicMock(spec=FeatureFlagConfigurationSetting)
    kv.key = f".appconfig.featureflag/{feature_id}"
    kv.feature_id = feature_id
    kv.enabled = enabled
    kv.value = f'{{"id":"{feature_id}","enabled":{str(enabled).lower()}}}'
    return kv


@pytest.mark.asyncio
async def test_load_caches_feature_flag_settings():
    """Feature flags returned as FeatureFlagConfigurationSetting are cached."""
    svc = AppConfigService()
    mock_client = AsyncMock()
    mock_client.list_configuration_settings = MagicMock(
        return_value=_async_iter([
            _make_kv("regular.setting", "value"),
            _make_feature_flag_kv("displayProductLandingPage", True),
        ])
    )

    with (
        patch.object(_config.settings, "app_config_endpoint", "https://appcs-test.azconfig.io"),
        patch.object(svc, "_get_client", new_callable=AsyncMock, return_value=mock_client),
    ):
        await svc.ensure_loaded()

    assert svc.get("regular.setting") == "value"
    flags = svc.get_feature_flags()
    assert flags["displayProductLandingPage"] is True


@pytest.mark.asyncio
async def test_load_feature_flag_fallback_when_value_is_none():
    """Feature flags with value=None fall back to typed field extraction."""
    svc = AppConfigService()

    ff_kv = _make_feature_flag_kv("myFlag", True)
    ff_kv.value = None  # Simulate SDK returning None for value

    mock_client = AsyncMock()
    mock_client.list_configuration_settings = MagicMock(
        return_value=_async_iter([ff_kv])
    )

    with (
        patch.object(_config.settings, "app_config_endpoint", "https://appcs-test.azconfig.io"),
        patch.object(svc, "_get_client", new_callable=AsyncMock, return_value=mock_client),
    ):
        await svc.ensure_loaded()

    # The flag should still be in the cache despite value being None
    flags = svc.get_feature_flags()
    assert flags["myFlag"] is True


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
async def test_close_releases_client_and_credential():
    """close() closes both the SDK client and the credential."""
    svc = AppConfigService()
    mock_client = AsyncMock()
    mock_credential = AsyncMock()
    svc._client = mock_client
    svc._credential = mock_credential
    svc._loaded = True

    await svc.close()

    mock_client.close.assert_awaited_once()
    mock_credential.close.assert_awaited_once()
    assert svc._client is None
    assert svc._credential is None
    assert svc._loaded is False


@pytest.mark.asyncio
async def test_close_is_safe_when_never_initialized():
    """close() is a no-op when the client was never created."""
    svc = AppConfigService()
    await svc.close()  # must not raise

