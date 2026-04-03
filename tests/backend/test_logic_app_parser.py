"""Tests for the Logic App workflow parser."""

from pathlib import Path

import pytest

from workers.parser.parsers.logic_app import LogicAppParser

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def parser():
    return LogicAppParser()


@pytest.fixture
def workflow_content():
    return (FIXTURES / "logic_app_workflow.json").read_bytes()


class TestLogicAppParser:
    """Tests for LogicAppParser component and edge extraction."""

    def test_extracts_workflow_component(self, parser, workflow_content):
        result = parser.parse(workflow_content, "order-processor.json")
        workflows = [c for c in result.components if c.component_type == "logic_app_workflow"]
        assert len(workflows) == 1
        wf = workflows[0]
        assert wf.name == "order-processor.json"
        assert wf.properties["triggerCount"] == 1
        assert wf.properties["actionCount"] == 3

    def test_extracts_trigger(self, parser, workflow_content):
        result = parser.parse(workflow_content, "order-processor.json")
        triggers = [c for c in result.components if c.component_type == "logic_app_trigger"]
        assert len(triggers) == 1
        assert triggers[0].name == "manual"
        assert triggers[0].properties["type"] == "Request"

    def test_extracts_actions(self, parser, workflow_content):
        result = parser.parse(workflow_content, "order-processor.json")
        actions = [c for c in result.components if c.component_type == "logic_app_action"]
        assert len(actions) == 3
        names = {a.name for a in actions}
        assert names == {"Get_Order_Details", "Send_To_ServiceBus", "Notify_Webhook"}

    def test_http_action_properties(self, parser, workflow_content):
        result = parser.parse(workflow_content, "order-processor.json")
        http_actions = [
            c
            for c in result.components
            if c.component_type == "logic_app_action" and c.properties.get("type", "").lower() == "http"
        ]
        assert len(http_actions) == 2
        get_order = next(a for a in http_actions if a.name == "Get_Order_Details")
        assert get_order.properties["method"] == "GET"
        assert get_order.properties["uri"].startswith("https://api.orders.example.com/")

    def test_workflow_to_trigger_edges(self, parser, workflow_content):
        result = parser.parse(workflow_content, "order-processor.json")
        trigger_edges = [e for e in result.edges if e.edge_type == "triggers"]
        assert len(trigger_edges) == 1

    def test_workflow_to_action_edges(self, parser, workflow_content):
        result = parser.parse(workflow_content, "order-processor.json")
        call_edges = [e for e in result.edges if e.edge_type == "calls"]
        assert len(call_edges) == 3

    def test_run_after_edges(self, parser, workflow_content):
        result = parser.parse(workflow_content, "order-processor.json")
        run_after_edges = [e for e in result.edges if e.edge_type == "runs_after"]
        # Send_To_ServiceBus runAfter Get_Order_Details
        # Notify_Webhook runAfter Send_To_ServiceBus
        assert len(run_after_edges) == 2

    def test_external_references_from_http(self, parser, workflow_content):
        result = parser.parse(workflow_content, "order-processor.json")
        ext_names = {r.name for r in result.external_references}
        assert "api.orders.example.com" in ext_names
        assert "hooks.slack.example.com" in ext_names

    def test_external_references_from_servicebus(self, parser, workflow_content):
        result = parser.parse(workflow_content, "order-processor.json")
        sb_refs = [r for r in result.external_references if "servicebus" in r.name.lower()]
        assert len(sb_refs) >= 1

    def test_invalid_json_raises_value_error(self, parser):
        with pytest.raises(ValueError, match="Invalid JSON"):
            parser.parse(b"not valid json!", "bad.json")

    def test_minimal_workflow_no_triggers(self, parser):
        content = b'{"definition": {"actions": {}}}'
        result = parser.parse(content, "empty.json")
        workflows = [c for c in result.components if c.component_type == "logic_app_workflow"]
        assert len(workflows) == 1
        assert workflows[0].properties["triggerCount"] == 0

    def test_root_level_definition(self, parser):
        """When definition is at root level (no wrapper), it should still parse."""
        content = b'{"triggers": {"t1": {"type": "Recurrence"}}, "actions": {}}'
        result = parser.parse(content, "root.json")
        triggers = [c for c in result.components if c.component_type == "logic_app_trigger"]
        assert len(triggers) == 1
        assert triggers[0].properties["type"] == "Recurrence"
