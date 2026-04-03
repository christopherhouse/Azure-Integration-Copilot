"""APIM policy XML parser — extracts policy sections and referenced backends."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from workers.parser.models import ExternalReference, ParsedComponent, ParsedEdge, ParseResult
from workers.parser.parsers.base import BaseParser

# Recognised APIM policy section names.
_SECTIONS = {"inbound", "outbound", "backend", "on-error"}


class ApimPolicyParser(BaseParser):
    """Parse APIM policy XML documents."""

    def parse(self, content: bytes, filename: str) -> ParseResult:
        """Parse an APIM policy XML and extract sections, policies, and backends."""
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid XML in {filename}: {exc}") from exc

        if root.tag != "policies":
            raise ValueError(f"Expected <policies> root element in {filename}, got <{root.tag}>.")

        components: list[ParsedComponent] = []
        edges: list[ParsedEdge] = []
        external_refs: list[ExternalReference] = []

        policy_root_id = "policy_0"
        components.append(
            ParsedComponent(
                tempId=policy_root_id,
                componentType="apim_policy",
                name=filename,
                displayName=filename,
                properties={
                    "sections": [s.tag for s in root if s.tag in _SECTIONS],
                },
            )
        )

        comp_idx = 1

        for section in root:
            if section.tag not in _SECTIONS:
                continue

            section_id = f"policy_{comp_idx}"
            comp_idx += 1

            child_names = [child.tag for child in section]
            components.append(
                ParsedComponent(
                    tempId=section_id,
                    componentType="apim_policy_section",
                    name=section.tag,
                    displayName=f"Section: {section.tag}",
                    properties={
                        "section": section.tag,
                        "policyCount": len(child_names),
                        "policies": child_names,
                    },
                )
            )
            edges.append(
                ParsedEdge(
                    sourceTempId=policy_root_id,
                    targetTempId=section_id,
                    edgeType="has_section",
                )
            )

            # Inspect children for backend references and named policies
            for child in section:
                _collect_backend_refs(child, external_refs)

        return ParseResult(
            artifactId="",
            artifactType="apim_policy",
            components=components,
            edges=edges,
            externalReferences=external_refs,
        )


def _collect_backend_refs(
    element: ET.Element,
    refs: list[ExternalReference],
) -> None:
    """Recursively collect external references from backend URLs in XML elements."""
    # <set-backend-service base-url="...">
    if element.tag == "set-backend-service":
        url = element.get("base-url", "")
        if url:
            host = _extract_host(url)
            if host:
                refs.append(
                    ExternalReference(
                        tempId=f"ext_{len(refs)}",
                        name=host,
                        displayName=f"Backend: {host}",
                        inferredFrom="set-backend-service:base-url",
                    )
                )

    # <send-request> with <set-url>
    if element.tag == "send-request":
        for child in element:
            if child.tag == "set-url" and child.text:
                host = _extract_host(child.text.strip())
                if host:
                    refs.append(
                        ExternalReference(
                            tempId=f"ext_{len(refs)}",
                            name=host,
                            displayName=f"Backend: {host}",
                            inferredFrom="send-request:set-url",
                        )
                    )

    # Recurse into children
    for child in element:
        _collect_backend_refs(child, refs)


def _extract_host(uri: str) -> str:
    """Extract the hostname from a URI, returning empty string on failure."""
    try:
        parsed = urlparse(uri)
        return parsed.hostname or ""
    except Exception:
        return ""
