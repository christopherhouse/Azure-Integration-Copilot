package graph

import "testing"

func TestGenerateComponentID_Deterministic(t *testing.T) {
	id1 := GenerateComponentID("t1", "p1", "logic_app_workflow", "my-workflow")
	id2 := GenerateComponentID("t1", "p1", "logic_app_workflow", "my-workflow")
	if id1 != id2 {
		t.Errorf("same inputs must produce same output: %q != %q", id1, id2)
	}
}

func TestGenerateComponentID_Prefix(t *testing.T) {
	id := GenerateComponentID("t1", "p1", "api", "my-api")
	if len(id) < 4 || id[:4] != "cmp_" {
		t.Errorf("expected cmp_ prefix, got %q", id)
	}
	// Should be cmp_ + 20 hex chars = 24 total
	if len(id) != 24 {
		t.Errorf("expected length 24, got %d: %q", len(id), id)
	}
}

func TestGenerateComponentID_MatchesPython(t *testing.T) {
	// Verified against Python: generate_component_id("t1","p1","logic_app_workflow","my-workflow")
	got := GenerateComponentID("t1", "p1", "logic_app_workflow", "my-workflow")
	want := "cmp_a2256abf225d07075d47"
	if got != want {
		t.Errorf("got %q, want %q", got, want)
	}

	// Verified against Python: generate_component_id("t1","p1","api","my-api")
	got2 := GenerateComponentID("t1", "p1", "api", "my-api")
	want2 := "cmp_ef4db955ac25e1bbd40a"
	if got2 != want2 {
		t.Errorf("got %q, want %q", got2, want2)
	}
}

func TestGenerateComponentID_DifferentInputs(t *testing.T) {
	id1 := GenerateComponentID("t1", "p1", "api", "service-a")
	id2 := GenerateComponentID("t1", "p1", "api", "service-b")
	if id1 == id2 {
		t.Error("different inputs must produce different IDs")
	}
}

func TestGenerateEdgeID_Deterministic(t *testing.T) {
	id1 := GenerateEdgeID("cmp_abc", "cmp_def", "calls")
	id2 := GenerateEdgeID("cmp_abc", "cmp_def", "calls")
	if id1 != id2 {
		t.Errorf("same inputs must produce same output: %q != %q", id1, id2)
	}
}

func TestGenerateEdgeID_Prefix(t *testing.T) {
	id := GenerateEdgeID("cmp_abc", "cmp_def", "calls")
	if len(id) < 4 || id[:4] != "edg_" {
		t.Errorf("expected edg_ prefix, got %q", id)
	}
	if len(id) != 24 {
		t.Errorf("expected length 24, got %d: %q", len(id), id)
	}
}

func TestGenerateEdgeID_MatchesPython(t *testing.T) {
	// Verified against Python: generate_edge_id("cmp_abc123","cmp_def456","calls")
	got := GenerateEdgeID("cmp_abc123", "cmp_def456", "calls")
	want := "edg_233d4ab5a3d40059ce31"
	if got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func TestGenerateEdgeID_DifferentInputs(t *testing.T) {
	id1 := GenerateEdgeID("cmp_a", "cmp_b", "calls")
	id2 := GenerateEdgeID("cmp_a", "cmp_b", "triggers")
	if id1 == id2 {
		t.Error("different edge types must produce different IDs")
	}
}
