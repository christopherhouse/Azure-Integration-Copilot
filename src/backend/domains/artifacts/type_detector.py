"""Artifact type detection based on file extension and content inspection."""

import json

import structlog
import yaml
from fastapi import UploadFile

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Maximum bytes to read for content-based detection.
_DETECTION_HEAD = 8192


async def detect_artifact_type(filename: str, file: UploadFile) -> str:
    """Detect the artifact type from filename extension and content.

    After reading content for detection the file position is reset to 0
    so that callers can continue to stream the file for upload.
    """
    ext = _extension(filename)

    try:
        if ext in (".json", ".yaml", ".yml"):
            return await _detect_json_yaml(file, ext)
        if ext == ".xml":
            return await _detect_xml(file)
        if ext == ".tf":
            return "terraform"
        if ext == ".bicep":
            return "bicep"
    except Exception:
        logger.warning("type_detection_error", filename=filename, exc_info=True)
    finally:
        await file.seek(0)

    return "unknown"


def _extension(filename: str) -> str:
    """Return the lowercased file extension including the dot."""
    dot = filename.rfind(".")
    if dot == -1:
        return ""
    return filename[dot:].lower()


async def _detect_json_yaml(file: UploadFile, ext: str) -> str:
    """Detect Logic App workflows and OpenAPI specs from JSON/YAML content."""
    head = await file.read(_DETECTION_HEAD)
    if not head:
        return "unknown"

    text = head.decode("utf-8", errors="replace")

    try:
        if ext == ".json":
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except Exception:
        return "unknown"

    if not isinstance(data, dict):
        return "unknown"

    # Logic App workflow: has a "definition" key containing triggers/actions
    definition = data.get("definition")
    if isinstance(definition, dict) and ("triggers" in definition or "actions" in definition):
        return "logic_app_workflow"

    # OpenAPI / Swagger spec
    if "openapi" in data or "swagger" in data:
        return "openapi_spec"

    return "unknown"


async def _detect_xml(file: UploadFile) -> str:
    """Detect APIM policies from XML content."""
    head = await file.read(_DETECTION_HEAD)
    if not head:
        return "unknown"

    text = head.decode("utf-8", errors="replace").strip()

    # Simple heuristic: look for <policies> root element
    if "<policies" in text:
        return "apim_policy"

    return "unknown"
