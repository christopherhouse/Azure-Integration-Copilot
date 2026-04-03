"""Logic App workflow parser — extracts triggers, actions, and connections."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from workers.parser.models import ExternalReference, ParsedComponent, ParsedEdge, ParseResult
from workers.parser.parsers.base import BaseParser


class LogicAppParser(BaseParser):
    """Parse Logic App workflow JSON definitions."""

    def parse(self, content: bytes, filename: str) -> ParseResult:
        """Parse a Logic App workflow definition and extract components/edges."""
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"Invalid JSON in {filename}: {exc}") from exc

        definition = data.get("definition", data)
        triggers: dict[str, Any] = definition.get("triggers", {})
        actions: dict[str, Any] = definition.get("actions", {})

        components: list[ParsedComponent] = []
        edges: list[ParsedEdge] = []
        external_refs: list[ExternalReference] = []

        # Workflow component
        workflow_id = "workflow_0"
        components.append(
            ParsedComponent(
                tempId=workflow_id,
                componentType="logic_app_workflow",
                name=filename,
                displayName=filename,
                properties={
                    "triggerCount": len(triggers),
                    "actionCount": len(actions),
                    "triggerType": next(iter(triggers.values()), {}).get("type", "unknown") if triggers else "none",
                },
            )
        )

        # Triggers
        for idx, (trigger_name, trigger_def) in enumerate(triggers.items()):
            trigger_id = f"trigger_{idx}"
            trigger_type = trigger_def.get("type", "unknown") if isinstance(trigger_def, dict) else "unknown"
            components.append(
                ParsedComponent(
                    tempId=trigger_id,
                    componentType="logic_app_trigger",
                    name=trigger_name,
                    displayName=trigger_name,
                    properties={"type": trigger_type},
                )
            )
            edges.append(
                ParsedEdge(
                    sourceTempId=workflow_id,
                    targetTempId=trigger_id,
                    edgeType="triggers",
                )
            )

        # Actions
        action_ids: dict[str, str] = {}
        for idx, (action_name, action_def) in enumerate(actions.items()):
            action_id = f"action_{idx}"
            action_ids[action_name] = action_id

            action_type = action_def.get("type", "unknown") if isinstance(action_def, dict) else "unknown"
            props: dict[str, Any] = {"type": action_type}

            if isinstance(action_def, dict) and action_type.lower() == "http":
                method = action_def.get("inputs", {}).get("method", "")
                uri = action_def.get("inputs", {}).get("uri", "")
                props["method"] = method
                props["uri"] = uri

            components.append(
                ParsedComponent(
                    tempId=action_id,
                    componentType="logic_app_action",
                    name=action_name,
                    displayName=action_name,
                    properties=props,
                )
            )
            edges.append(
                ParsedEdge(
                    sourceTempId=workflow_id,
                    targetTempId=action_id,
                    edgeType="calls",
                )
            )

        # Action → action edges based on runAfter
        for action_name, action_def in actions.items():
            if not isinstance(action_def, dict):
                continue
            run_after: dict[str, Any] = action_def.get("runAfter", {})
            for dep_name in run_after:
                source_id = action_ids.get(dep_name)
                target_id = action_ids.get(action_name)
                if source_id and target_id:
                    edges.append(
                        ParsedEdge(
                            sourceTempId=source_id,
                            targetTempId=target_id,
                            edgeType="runs_after",
                        )
                    )

        # Infer external references from HTTP URIs
        ext_idx = 0
        for action_name, action_def in actions.items():
            if not isinstance(action_def, dict):
                continue
            action_type = action_def.get("type", "")
            if action_type.lower() == "http":
                uri = action_def.get("inputs", {}).get("uri", "")
                if uri:
                    host = _extract_host(uri)
                    if host:
                        external_refs.append(
                            ExternalReference(
                                tempId=f"ext_{ext_idx}",
                                name=host,
                                displayName=host,
                                inferredFrom=f"action:{action_name}:uri",
                            )
                        )
                        ext_idx += 1

        # Infer external references from Service Bus connections
        connections = data.get("parameters", {}).get("$connections", {}).get("value", {})
        for conn_name, conn_def in connections.items():
            if not isinstance(conn_def, dict):
                continue
            conn_id = conn_def.get("connectionId", "")
            if "servicebus" in conn_id.lower() or "servicebus" in conn_name.lower():
                external_refs.append(
                    ExternalReference(
                        tempId=f"ext_{ext_idx}",
                        name=f"servicebus:{conn_name}",
                        displayName=f"Service Bus ({conn_name})",
                        inferredFrom=f"connection:{conn_name}",
                    )
                )
                ext_idx += 1

        return ParseResult(
            artifactId="",
            artifactType="logic_app_workflow",
            components=components,
            edges=edges,
            externalReferences=external_refs,
        )


def _extract_host(uri: str) -> str:
    """Extract the hostname from a URI, returning empty string on failure."""
    try:
        parsed = urlparse(uri)
        return parsed.hostname or ""
    except Exception:
        return ""
