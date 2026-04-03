"""OpenAPI / Swagger specification parser — extracts API definitions and operations."""

from __future__ import annotations

import json
from typing import Any

import yaml

from workers.parser.models import ExternalReference, ParsedComponent, ParsedEdge, ParseResult
from workers.parser.parsers.base import BaseParser


class OpenApiParser(BaseParser):
    """Parse OpenAPI v3 and Swagger v2 specifications (JSON and YAML)."""

    def parse(self, content: bytes, filename: str) -> ParseResult:
        """Parse an OpenAPI/Swagger spec and extract API definition and operations."""
        data = _load_content(content, filename)

        is_v3 = "openapi" in data
        is_v2 = "swagger" in data
        if not is_v3 and not is_v2:
            raise ValueError(f"Unrecognised API spec format in {filename}: missing 'openapi' or 'swagger' key.")

        components: list[ParsedComponent] = []
        edges: list[ParsedEdge] = []
        external_refs: list[ExternalReference] = []

        info: dict[str, Any] = data.get("info", {})
        title = info.get("title", filename)
        version = info.get("version", "unknown")

        # Determine base URL
        if is_v3:
            servers = data.get("servers", [])
            base_url = servers[0].get("url", "") if servers else ""
        else:
            host = data.get("host", "")
            base_path = data.get("basePath", "")
            schemes = data.get("schemes", ["https"])
            scheme = schemes[0] if schemes else "https"
            base_url = f"{scheme}://{host}{base_path}" if host else ""

        # Count operations
        paths: dict[str, Any] = data.get("paths", {})
        operation_count = 0
        for _path, methods in paths.items():
            if isinstance(methods, dict):
                for method in methods:
                    if method.lower() in {"get", "post", "put", "patch", "delete", "options", "head", "trace"}:
                        operation_count += 1

        # API definition component
        api_id = "api_0"
        components.append(
            ParsedComponent(
                tempId=api_id,
                componentType="api_definition",
                name=title,
                displayName=title,
                properties={
                    "title": title,
                    "version": version,
                    "baseUrl": base_url,
                    "operationCount": operation_count,
                    "specVersion": data.get("openapi", data.get("swagger", "unknown")),
                },
            )
        )

        # Operations
        op_idx = 0
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, op_def in methods.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head", "trace"}:
                    continue
                op_id = f"op_{op_idx}"
                summary = ""
                if isinstance(op_def, dict):
                    summary = op_def.get("summary", op_def.get("operationId", ""))
                components.append(
                    ParsedComponent(
                        tempId=op_id,
                        componentType="api_operation",
                        name=f"{method.upper()} {path}",
                        displayName=f"{method.upper()} {path}",
                        properties={
                            "method": method.upper(),
                            "path": path,
                            "summary": summary,
                        },
                    )
                )
                edges.append(
                    ParsedEdge(
                        sourceTempId=api_id,
                        targetTempId=op_id,
                        edgeType="has_operation",
                    )
                )
                op_idx += 1

        # External references from servers / host
        ext_idx = 0
        if is_v3:
            for server in data.get("servers", []):
                url = server.get("url", "")
                if url:
                    external_refs.append(
                        ExternalReference(
                            tempId=f"ext_{ext_idx}",
                            name=url,
                            displayName=f"Server: {url}",
                            inferredFrom="servers",
                        )
                    )
                    ext_idx += 1
        elif is_v2:
            host = data.get("host", "")
            if host:
                external_refs.append(
                    ExternalReference(
                        tempId=f"ext_{ext_idx}",
                        name=host,
                        displayName=f"Host: {host}",
                        inferredFrom="host",
                    )
                )
                ext_idx += 1

        return ParseResult(
            artifactId="",
            artifactType="openapi_spec",
            components=components,
            edges=edges,
            externalReferences=external_refs,
        )


def _load_content(content: bytes, filename: str) -> dict[str, Any]:
    """Load JSON or YAML content, auto-detecting format."""
    text = content.decode("utf-8")
    lower = filename.lower()

    if lower.endswith((".yaml", ".yml")):
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in {filename}: {exc}") from exc
    else:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"Invalid JSON in {filename}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON/YAML object in {filename}, got {type(data).__name__}.")
    return data
