"""Tests for the OpenAPI / Swagger parser."""

from pathlib import Path

import pytest

from workers.parser.parsers.openapi import OpenApiParser

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def parser():
    return OpenApiParser()


class TestOpenApiV3Json:
    """Tests for OpenAPI v3 JSON parsing."""

    @pytest.fixture
    def v3_content(self):
        return (FIXTURES / "openapi_v3.json").read_bytes()

    def test_extracts_api_definition(self, parser, v3_content):
        result = parser.parse(v3_content, "orders-api.json")
        apis = [c for c in result.components if c.component_type == "api_definition"]
        assert len(apis) == 1
        api = apis[0]
        assert api.name == "Order Management API"
        assert api.properties["version"] == "1.2.0"
        assert api.properties["operationCount"] == 4

    def test_extracts_operations(self, parser, v3_content):
        result = parser.parse(v3_content, "orders-api.json")
        ops = [c for c in result.components if c.component_type == "api_operation"]
        assert len(ops) == 4
        methods = {o.properties["method"] for o in ops}
        assert "GET" in methods
        assert "POST" in methods
        assert "DELETE" in methods

    def test_has_operation_edges(self, parser, v3_content):
        result = parser.parse(v3_content, "orders-api.json")
        edges = [e for e in result.edges if e.edge_type == "has_operation"]
        assert len(edges) == 4

    def test_server_external_reference(self, parser, v3_content):
        result = parser.parse(v3_content, "orders-api.json")
        refs = result.external_references
        assert len(refs) >= 1
        assert any("api.orders.example.com" in r.name for r in refs)

    def test_base_url_from_servers(self, parser, v3_content):
        result = parser.parse(v3_content, "orders-api.json")
        api = next(c for c in result.components if c.component_type == "api_definition")
        assert api.properties["baseUrl"] == "https://api.orders.example.com/v1"


class TestOpenApiV3Yaml:
    """Tests for OpenAPI v3 YAML parsing."""

    @pytest.fixture
    def v3_yaml_content(self):
        return (FIXTURES / "openapi_v3.yaml").read_bytes()

    def test_yaml_extracts_api_definition(self, parser, v3_yaml_content):
        result = parser.parse(v3_yaml_content, "orders-api.yaml")
        apis = [c for c in result.components if c.component_type == "api_definition"]
        assert len(apis) == 1
        assert apis[0].name == "Order Management API"

    def test_yaml_extracts_operations(self, parser, v3_yaml_content):
        result = parser.parse(v3_yaml_content, "orders-api.yaml")
        ops = [c for c in result.components if c.component_type == "api_operation"]
        assert len(ops) == 4

    def test_yaml_produces_same_result_as_json(self, parser, v3_yaml_content):
        json_content = (FIXTURES / "openapi_v3.json").read_bytes()
        json_result = parser.parse(json_content, "orders-api.json")
        yaml_result = parser.parse(v3_yaml_content, "orders-api.yaml")
        assert len(json_result.components) == len(yaml_result.components)
        assert len(json_result.edges) == len(yaml_result.edges)


class TestSwaggerV2:
    """Tests for Swagger v2 parsing."""

    def test_swagger_v2_json(self, parser):
        content = b"""{
            "swagger": "2.0",
            "info": {"title": "Legacy API", "version": "0.9"},
            "host": "legacy.example.com",
            "basePath": "/api",
            "schemes": ["https"],
            "paths": {
                "/items": {
                    "get": {"summary": "List items"}
                }
            }
        }"""
        result = parser.parse(content, "legacy.json")
        apis = [c for c in result.components if c.component_type == "api_definition"]
        assert len(apis) == 1
        assert apis[0].name == "Legacy API"
        assert apis[0].properties["baseUrl"] == "https://legacy.example.com/api"
        assert apis[0].properties["operationCount"] == 1

        # External reference from host
        refs = result.external_references
        assert any(r.name == "legacy.example.com" for r in refs)

    def test_swagger_v2_yaml(self, parser):
        content = b"""swagger: "2.0"
info:
  title: Legacy API
  version: "0.9"
host: legacy.example.com
basePath: /api
schemes:
  - https
paths:
  /items:
    get:
      summary: List items
"""
        result = parser.parse(content, "legacy.yaml")
        apis = [c for c in result.components if c.component_type == "api_definition"]
        assert len(apis) == 1
        assert apis[0].name == "Legacy API"
        ops = [c for c in result.components if c.component_type == "api_operation"]
        assert len(ops) == 1


class TestOpenApiParserErrors:
    """Tests for error handling."""

    def test_invalid_json_raises_value_error(self, parser):
        with pytest.raises(ValueError, match="Invalid JSON"):
            parser.parse(b"not json", "bad.json")

    def test_invalid_yaml_raises_value_error(self, parser):
        with pytest.raises(ValueError, match="Invalid YAML"):
            parser.parse(b":\n  :\n    - [invalid", "bad.yaml")

    def test_missing_spec_key_raises_value_error(self, parser):
        with pytest.raises(ValueError, match="missing 'openapi' or 'swagger'"):
            parser.parse(b'{"info": {"title": "test"}}', "missing.json")

    def test_non_object_raises_value_error(self, parser):
        with pytest.raises(ValueError, match="Expected a JSON/YAML object"):
            parser.parse(b"[1,2,3]", "array.json")
