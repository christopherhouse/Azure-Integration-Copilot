"""Tests for deterministic component and edge ID generation."""

import os
from unittest.mock import patch

_test_env = {
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "https://fake-eg.westus-1.eventgrid.azure.net",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from domains.graph.id_generation import generate_component_id, generate_edge_id


class TestGenerateComponentId:
    """Tests for generate_component_id."""

    def test_returns_prefixed_id(self):
        result = generate_component_id("t1", "p1", "logic_app_workflow", "my-workflow")
        assert result.startswith("cmp_")

    def test_deterministic_same_input(self):
        id1 = generate_component_id("t1", "p1", "logic_app_workflow", "my-workflow")
        id2 = generate_component_id("t1", "p1", "logic_app_workflow", "my-workflow")
        assert id1 == id2

    def test_different_names_produce_different_ids(self):
        id1 = generate_component_id("t1", "p1", "logic_app_workflow", "workflow-a")
        id2 = generate_component_id("t1", "p1", "logic_app_workflow", "workflow-b")
        assert id1 != id2

    def test_different_types_produce_different_ids(self):
        id1 = generate_component_id("t1", "p1", "logic_app_workflow", "my-item")
        id2 = generate_component_id("t1", "p1", "api_definition", "my-item")
        assert id1 != id2

    def test_different_projects_produce_different_ids(self):
        id1 = generate_component_id("t1", "p1", "logic_app_workflow", "my-workflow")
        id2 = generate_component_id("t1", "p2", "logic_app_workflow", "my-workflow")
        assert id1 != id2

    def test_different_tenants_produce_different_ids(self):
        id1 = generate_component_id("t1", "p1", "logic_app_workflow", "my-workflow")
        id2 = generate_component_id("t2", "p1", "logic_app_workflow", "my-workflow")
        assert id1 != id2

    def test_id_length_is_fixed(self):
        result = generate_component_id("t1", "p1", "logic_app_workflow", "my-workflow")
        # "cmp_" (4 chars) + 20 hex chars = 24 chars
        assert len(result) == 24

    def test_id_contains_only_valid_characters(self):
        result = generate_component_id("t1", "p1", "logic_app_workflow", "my-workflow")
        prefix = result[:4]
        hash_part = result[4:]
        assert prefix == "cmp_"
        assert all(c in "0123456789abcdef" for c in hash_part)


class TestGenerateEdgeId:
    """Tests for generate_edge_id."""

    def test_returns_prefixed_id(self):
        result = generate_edge_id("cmp_src", "cmp_tgt", "calls")
        assert result.startswith("edg_")

    def test_deterministic_same_input(self):
        id1 = generate_edge_id("cmp_src", "cmp_tgt", "calls")
        id2 = generate_edge_id("cmp_src", "cmp_tgt", "calls")
        assert id1 == id2

    def test_different_sources_produce_different_ids(self):
        id1 = generate_edge_id("cmp_src1", "cmp_tgt", "calls")
        id2 = generate_edge_id("cmp_src2", "cmp_tgt", "calls")
        assert id1 != id2

    def test_different_targets_produce_different_ids(self):
        id1 = generate_edge_id("cmp_src", "cmp_tgt1", "calls")
        id2 = generate_edge_id("cmp_src", "cmp_tgt2", "calls")
        assert id1 != id2

    def test_different_types_produce_different_ids(self):
        id1 = generate_edge_id("cmp_src", "cmp_tgt", "calls")
        id2 = generate_edge_id("cmp_src", "cmp_tgt", "triggers")
        assert id1 != id2

    def test_direction_matters(self):
        """Edge from A→B is different from B→A."""
        id1 = generate_edge_id("cmp_a", "cmp_b", "calls")
        id2 = generate_edge_id("cmp_b", "cmp_a", "calls")
        assert id1 != id2

    def test_id_length_is_fixed(self):
        result = generate_edge_id("cmp_src", "cmp_tgt", "calls")
        # "edg_" (4 chars) + 20 hex chars = 24 chars
        assert len(result) == 24
