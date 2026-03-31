"""Tests for artifact type detection."""

import io
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

from domains.artifacts.type_detector import detect_artifact_type  # noqa: E402
from fastapi import UploadFile  # noqa: E402


def _make_upload(content: bytes, filename: str) -> UploadFile:
    """Create a FastAPI UploadFile backed by an in-memory BytesIO."""
    return UploadFile(filename=filename, file=io.BytesIO(content))


# ---------------------------------------------------------------------------
# Logic App workflow detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_logic_app_workflow_json():
    """JSON file with definition.triggers should be detected as logic_app_workflow."""
    workflow = json.dumps({
        "definition": {
            "triggers": {"manual": {"type": "Request"}},
            "actions": {"response": {"type": "Response"}},
        }
    }).encode()
    upload = _make_upload(workflow, "workflow.json")
    result = await detect_artifact_type("workflow.json", upload)
    assert result == "logic_app_workflow"


@pytest.mark.asyncio
async def test_detect_logic_app_workflow_yaml():
    """YAML file with definition.triggers should be detected as logic_app_workflow."""
    workflow = yaml.dump({
        "definition": {
            "triggers": {"manual": {"type": "Request"}},
            "actions": {"response": {"type": "Response"}},
        }
    }).encode()
    upload = _make_upload(workflow, "workflow.yaml")
    result = await detect_artifact_type("workflow.yaml", upload)
    assert result == "logic_app_workflow"


# ---------------------------------------------------------------------------
# OpenAPI spec detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_openapi_json():
    """JSON file with 'openapi' key should be detected as openapi_spec."""
    spec = json.dumps({"openapi": "3.0.0", "info": {"title": "Test"}}).encode()
    upload = _make_upload(spec, "api.json")
    result = await detect_artifact_type("api.json", upload)
    assert result == "openapi_spec"


@pytest.mark.asyncio
async def test_detect_swagger_yaml():
    """YAML file with 'swagger' key should be detected as openapi_spec."""
    spec = yaml.dump({"swagger": "2.0", "info": {"title": "Test"}}).encode()
    upload = _make_upload(spec, "api.yml")
    result = await detect_artifact_type("api.yml", upload)
    assert result == "openapi_spec"


# ---------------------------------------------------------------------------
# APIM policy detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_apim_policy_xml():
    """XML file with <policies> root should be detected as apim_policy."""
    xml = b'<policies><inbound><base /></inbound></policies>'
    upload = _make_upload(xml, "policy.xml")
    result = await detect_artifact_type("policy.xml", upload)
    assert result == "apim_policy"


@pytest.mark.asyncio
async def test_detect_xml_without_policies():
    """XML file without <policies> should be unknown."""
    xml = b'<configuration><setting key="a" value="b" /></configuration>'
    upload = _make_upload(xml, "config.xml")
    result = await detect_artifact_type("config.xml", upload)
    assert result == "unknown"


# ---------------------------------------------------------------------------
# Unknown / unsupported file types
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_unknown_txt():
    """A .txt file should be detected as unknown."""
    upload = _make_upload(b"Hello world", "readme.txt")
    result = await detect_artifact_type("readme.txt", upload)
    assert result == "unknown"


@pytest.mark.asyncio
async def test_detect_unknown_json_without_markers():
    """A JSON file without workflow or OpenAPI markers should be unknown."""
    data = json.dumps({"name": "test", "value": 42}).encode()
    upload = _make_upload(data, "data.json")
    result = await detect_artifact_type("data.json", upload)
    assert result == "unknown"


# ---------------------------------------------------------------------------
# File position reset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_position_reset_after_detection():
    """File position should be at 0 after detection, regardless of type."""
    content = json.dumps({"openapi": "3.0.0"}).encode()
    upload = _make_upload(content, "spec.json")
    await detect_artifact_type("spec.json", upload)
    # Verify the full content is still readable from position 0
    data = await upload.read()
    assert data == content


# ---------------------------------------------------------------------------
# Extension-only detection (stretch types)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_terraform():
    """.tf files should be detected as terraform."""
    upload = _make_upload(b'resource "azurerm_resource_group" {}', "main.tf")
    result = await detect_artifact_type("main.tf", upload)
    assert result == "terraform"


@pytest.mark.asyncio
async def test_detect_bicep():
    """.bicep files should be detected as bicep."""
    upload = _make_upload(b"param location string", "main.bicep")
    result = await detect_artifact_type("main.bicep", upload)
    assert result == "bicep"
