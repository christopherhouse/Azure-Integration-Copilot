"""Tests for the APIM policy XML parser."""

from pathlib import Path

import pytest

from workers.parser.parsers.apim_policy import ApimPolicyParser

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def parser():
    return ApimPolicyParser()


@pytest.fixture
def policy_content():
    return (FIXTURES / "apim_policy.xml").read_bytes()


class TestApimPolicyParser:
    """Tests for APIM policy component extraction."""

    def test_extracts_root_policy_component(self, parser, policy_content):
        result = parser.parse(policy_content, "api-policy.xml")
        roots = [c for c in result.components if c.component_type == "apim_policy"]
        assert len(roots) == 1
        root = roots[0]
        assert root.name == "api-policy.xml"
        assert "inbound" in root.properties["sections"]
        assert "backend" in root.properties["sections"]
        assert "outbound" in root.properties["sections"]
        assert "on-error" in root.properties["sections"]

    def test_extracts_section_components(self, parser, policy_content):
        result = parser.parse(policy_content, "api-policy.xml")
        sections = [c for c in result.components if c.component_type == "apim_policy_section"]
        assert len(sections) == 4
        section_names = {s.name for s in sections}
        assert section_names == {"inbound", "backend", "outbound", "on-error"}

    def test_inbound_section_policies(self, parser, policy_content):
        result = parser.parse(policy_content, "api-policy.xml")
        inbound = next(c for c in result.components if c.name == "inbound")
        assert "rate-limit" in inbound.properties["policies"]
        assert "cors" in inbound.properties["policies"]
        assert "set-header" in inbound.properties["policies"]

    def test_has_section_edges(self, parser, policy_content):
        result = parser.parse(policy_content, "api-policy.xml")
        edges = [e for e in result.edges if e.edge_type == "has_section"]
        assert len(edges) == 4

    def test_backend_external_reference(self, parser, policy_content):
        result = parser.parse(policy_content, "api-policy.xml")
        backend_refs = [r for r in result.external_references if r.name == "backend-api.internal.example.com"]
        assert len(backend_refs) >= 1

    def test_send_request_external_reference(self, parser, policy_content):
        result = parser.parse(policy_content, "api-policy.xml")
        alert_refs = [r for r in result.external_references if r.name == "alerts.monitoring.example.com"]
        assert len(alert_refs) >= 1

    def test_invalid_xml_raises_value_error(self, parser):
        with pytest.raises(ValueError, match="Invalid XML"):
            parser.parse(b"<not-xml>", "bad.xml")

    def test_wrong_root_raises_value_error(self, parser):
        with pytest.raises(ValueError, match="Expected <policies>"):
            parser.parse(b"<root><child/></root>", "wrong.xml")

    def test_minimal_policy(self, parser):
        content = b"<policies><inbound><base /></inbound></policies>"
        result = parser.parse(content, "minimal.xml")
        sections = [c for c in result.components if c.component_type == "apim_policy_section"]
        assert len(sections) == 1
        assert sections[0].name == "inbound"
