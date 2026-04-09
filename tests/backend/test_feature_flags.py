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


def test_get_feature_flags_empty_when_no_flags(client):
    """Returns an empty flags map when App Config has no feature flags."""
    with patch.object(app_config_service, "get_feature_flags", return_value={}):
        response = client.get("/api/v1/feature-flags")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["flags"] == {}


def test_get_feature_flags_returns_boolean_flags(client):
    """Feature flags from App Config are returned as booleans."""
    flags_result = {
        "new-dashboard": True,
        "dark-mode": False,
        "beta-analysis": True,
    }
    with patch.object(app_config_service, "get_feature_flags", return_value=flags_result):
        response = client.get("/api/v1/feature-flags")

    assert response.status_code == 200
    flags = response.json()["data"]["flags"]
    assert set(flags.keys()) == {"new-dashboard", "dark-mode", "beta-analysis"}
    assert flags["new-dashboard"] is True
    assert flags["dark-mode"] is False
    assert flags["beta-analysis"] is True


def test_get_feature_flags_prefix_stripped(client):
    """The '.appconfig.featureflag/' prefix is stripped from flag names."""
    with patch.object(
        app_config_service,
        "get_feature_flags",
        return_value={"my-flag": True},
    ):
        response = client.get("/api/v1/feature-flags")

    flags = response.json()["data"]["flags"]
    assert "my-flag" in flags
    assert ".appconfig.featureflag/my-flag" not in flags


def test_get_feature_flags_disabled_flags(client):
    """Disabled flags are returned as False."""
    flags_result = {
        "flag-a": False,
        "flag-b": False,
        "flag-c": False,
    }
    with patch.object(app_config_service, "get_feature_flags", return_value=flags_result):
        response = client.get("/api/v1/feature-flags")

    flags = response.json()["data"]["flags"]
    assert flags["flag-a"] is False
    assert flags["flag-b"] is False
    assert flags["flag-c"] is False


def test_get_feature_flags_response_has_meta(client):
    """Response includes the standard meta envelope."""
    with patch.object(app_config_service, "get_feature_flags", return_value={}):
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
        patch.object(app_config_service, "get_feature_flags", return_value={}),
    ):
        client.get("/api/v1/feature-flags")

    assert ensure_loaded_called
