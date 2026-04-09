"""Tests for the feature flags API endpoint."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_test_env = {
    "ENVIRONMENT": "test",
    "COSMOS_DB_ENDPOINT": "",
    "BLOB_STORAGE_ENDPOINT": "",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "",
    "WEB_PUBSUB_ENDPOINT": "",
    "AZURE_CLIENT_ID": "",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
    "SKIP_AUTH": "true",
    "APP_CONFIG_ENDPOINT": "",
}

with patch.dict(os.environ, _test_env):
    from main import app  # noqa: E402
    from shared.app_config import app_config_service  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/v1/feature-flags — happy path
# ---------------------------------------------------------------------------


def test_get_feature_flags_empty_when_no_cache(client):
    """Returns an empty flags map when App Config has no feature.* keys."""
    with patch.object(app_config_service, "get_by_prefix", return_value={}):
        response = client.get("/api/v1/feature-flags")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["flags"] == {}


def test_get_feature_flags_returns_boolean_flags(client):
    """feature.* keys from App Config are returned as booleans."""
    prefix_result = {
        "feature.new-dashboard": "true",
        "feature.dark-mode": "false",
        "feature.beta-analysis": "True",  # case-insensitive
    }
    with patch.object(app_config_service, "get_by_prefix", return_value=prefix_result):
        response = client.get("/api/v1/feature-flags")

    assert response.status_code == 200
    flags = response.json()["data"]["flags"]
    assert set(flags.keys()) == {"new-dashboard", "dark-mode", "beta-analysis"}
    assert flags["new-dashboard"] is True
    assert flags["dark-mode"] is False
    assert flags["beta-analysis"] is True


def test_get_feature_flags_non_feature_keys_excluded(client):
    """Only keys returned by get_by_prefix('feature.') are included."""
    # The router delegates filtering to get_by_prefix, so non-feature keys
    # must not appear. Simulate get_by_prefix correctly returning only
    # feature-prefixed keys.
    with patch.object(
        app_config_service,
        "get_by_prefix",
        return_value={"feature.my-flag": "true"},
    ) as mock_gbp:
        response = client.get("/api/v1/feature-flags")

    # get_by_prefix was called with the feature prefix
    mock_gbp.assert_called_once_with("feature.")
    flags = response.json()["data"]["flags"]
    assert "my-flag" in flags
    assert "feature.my-flag" not in flags


def test_get_feature_flags_strips_feature_prefix(client):
    """The 'feature.' prefix is stripped from returned flag names."""
    with patch.object(
        app_config_service,
        "get_by_prefix",
        return_value={"feature.my-flag": "true"},
    ):
        response = client.get("/api/v1/feature-flags")

    flags = response.json()["data"]["flags"]
    assert "my-flag" in flags
    assert "feature.my-flag" not in flags


def test_get_feature_flags_non_true_values_are_false(client):
    """Values other than 'true' (case-insensitive) are treated as disabled."""
    prefix_result = {
        "feature.flag-a": "1",
        "feature.flag-b": "yes",
        "feature.flag-c": "enabled",
        "feature.flag-d": "",
    }
    with patch.object(app_config_service, "get_by_prefix", return_value=prefix_result):
        response = client.get("/api/v1/feature-flags")

    flags = response.json()["data"]["flags"]
    assert flags["flag-a"] is False
    assert flags["flag-b"] is False
    assert flags["flag-c"] is False
    assert flags["flag-d"] is False


def test_get_feature_flags_response_has_meta(client):
    """Response includes the standard meta envelope."""
    with patch.object(app_config_service, "get_by_prefix", return_value={}):
        response = client.get("/api/v1/feature-flags")

    body = response.json()
    assert "meta" in body
    assert "request_id" in body["meta"]
    assert "timestamp" in body["meta"]


def test_get_feature_flags_calls_ensure_loaded(client):
    """The endpoint calls ensure_loaded so flags are populated before access."""
    ensure_loaded_called = False

    async def _fake_ensure_loaded():
        nonlocal ensure_loaded_called
        ensure_loaded_called = True

    with (
        patch.object(app_config_service, "ensure_loaded", side_effect=_fake_ensure_loaded),
        patch.object(app_config_service, "get_by_prefix", return_value={}),
    ):
        client.get("/api/v1/feature-flags")

    assert ensure_loaded_called
