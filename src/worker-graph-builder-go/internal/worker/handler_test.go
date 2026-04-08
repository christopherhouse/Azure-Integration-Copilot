package worker

import (
	"context"
	"testing"

	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/azure/cosmos"
	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/azure/eventgrid"
)

// --- Mock implementations ---

type mockCosmos struct {
	readItems     map[string]map[string]any // key: "db/container/id/pk"
	upsertedItems []map[string]any
	replacedItems []map[string]any
	queryResults  []map[string]any
	sprocResult   map[string]any
}

func (m *mockCosmos) ReadItem(_ context.Context, database, container, id, partitionKey string) (map[string]any, error) {
	key := database + "/" + container + "/" + id + "/" + partitionKey
	if doc, ok := m.readItems[key]; ok {
		return doc, nil
	}
	return nil, nil
}

func (m *mockCosmos) CreateItem(_ context.Context, _, _, _ string, doc map[string]any) (map[string]any, error) {
	return doc, nil
}

func (m *mockCosmos) ReplaceItem(_ context.Context, _, _, _, _ string, doc map[string]any, _ string) (map[string]any, error) {
	m.replacedItems = append(m.replacedItems, doc)
	return doc, nil
}

func (m *mockCosmos) UpsertItem(_ context.Context, _, _, _ string, doc map[string]any) (map[string]any, error) {
	m.upsertedItems = append(m.upsertedItems, doc)
	return doc, nil
}

func (m *mockCosmos) QueryItems(_ context.Context, _, _, _, _ string, _ []cosmos.QueryParam) ([]map[string]any, error) {
	return m.queryResults, nil
}

func (m *mockCosmos) ExecuteStoredProcedure(_ context.Context, _, _, _, _ string, _ []any) (map[string]any, error) {
	if m.sprocResult != nil {
		return m.sprocResult, nil
	}
	return map[string]any{
		"componentCounts": map[string]any{},
		"edgeCounts":      map[string]any{},
		"totalComponents": float64(0),
		"totalEdges":      float64(0),
	}, nil
}

type mockPublisher struct {
	published []eventgrid.CloudEventOut
}

func (p *mockPublisher) PublishEvent(_ context.Context, event eventgrid.CloudEventOut) error {
	p.published = append(p.published, event)
	return nil
}

// --- Tests ---

func TestIsAlreadyProcessed_GraphBuilt(t *testing.T) {
	mc := &mockCosmos{
		readItems: map[string]map[string]any{
			DatabaseName + "/" + ProjectsContainer + "/art1/tenant1": {
				"id":     "art1",
				"status": "graph_built",
			},
		},
	}
	h := NewGraphBuilderHandler(mc, &mockPublisher{})
	eventData := map[string]any{"tenantId": "tenant1", "artifactId": "art1"}

	already, err := h.IsAlreadyProcessed(context.Background(), eventData)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !already {
		t.Error("expected already processed = true for graph_built status")
	}
}

func TestIsAlreadyProcessed_GraphFailed(t *testing.T) {
	mc := &mockCosmos{
		readItems: map[string]map[string]any{
			DatabaseName + "/" + ProjectsContainer + "/art2/tenant1": {
				"id":     "art2",
				"status": "graph_failed",
			},
		},
	}
	h := NewGraphBuilderHandler(mc, &mockPublisher{})
	eventData := map[string]any{"tenantId": "tenant1", "artifactId": "art2"}

	already, err := h.IsAlreadyProcessed(context.Background(), eventData)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !already {
		t.Error("expected already processed = true for graph_failed status")
	}
}

func TestIsAlreadyProcessed_Parsed(t *testing.T) {
	mc := &mockCosmos{
		readItems: map[string]map[string]any{
			DatabaseName + "/" + ProjectsContainer + "/art3/tenant1": {
				"id":     "art3",
				"status": "parsed",
			},
		},
	}
	h := NewGraphBuilderHandler(mc, &mockPublisher{})
	eventData := map[string]any{"tenantId": "tenant1", "artifactId": "art3"}

	already, err := h.IsAlreadyProcessed(context.Background(), eventData)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if already {
		t.Error("expected already processed = false for parsed status")
	}
}

func TestIsAlreadyProcessed_NotFound(t *testing.T) {
	mc := &mockCosmos{readItems: map[string]map[string]any{}}
	h := NewGraphBuilderHandler(mc, &mockPublisher{})
	eventData := map[string]any{"tenantId": "tenant1", "artifactId": "missing"}

	already, err := h.IsAlreadyProcessed(context.Background(), eventData)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if already {
		t.Error("expected already processed = false when artifact not found")
	}
}

func TestHandle_HappyPath(t *testing.T) {
	tenantID := "tenant1"
	projectID := "project1"
	artifactID := "artifact1"
	parseResultID := "pr1"

	mc := &mockCosmos{
		readItems: map[string]map[string]any{
			// Artifact
			DatabaseName + "/" + ProjectsContainer + "/" + artifactID + "/" + tenantID: {
				"id":     artifactID,
				"status": "parsed",
				"_etag":  `"etag1"`,
			},
			// Parse result
			DatabaseName + "/" + ProjectsContainer + "/" + parseResultID + "/" + tenantID: {
				"id":         parseResultID,
				"type":       "parse_result",
				"tenantId":   tenantID,
				"projectId":  projectID,
				"artifactId": artifactID,
				"components": []any{
					map[string]any{
						"tempId":        "tmp1",
						"componentType": "logic_app",
						"name":          "my-la",
						"displayName":   "My Logic App",
					},
				},
				"externalReferences": []any{},
				"edges":              []any{},
			},
			// Project
			DatabaseName + "/" + ProjectsContainer + "/" + projectID + "/" + tenantID: {
				"id":           projectID,
				"graphVersion": float64(0),
				"_etag":        `"etag2"`,
			},
		},
		sprocResult: map[string]any{
			"componentCounts": map[string]any{"logic_app": float64(1)},
			"edgeCounts":      map[string]any{},
			"totalComponents": float64(1),
			"totalEdges":      float64(0),
		},
	}
	pub := &mockPublisher{}
	h := NewGraphBuilderHandler(mc, pub)

	eventData := map[string]any{
		"tenantId":      tenantID,
		"projectId":     projectID,
		"artifactId":    artifactID,
		"parseResultId": parseResultID,
	}

	if err := h.Handle(context.Background(), eventData); err != nil {
		t.Fatalf("Handle returned error: %v", err)
	}

	// Verify GraphUpdated event was published.
	if len(pub.published) == 0 {
		t.Fatal("expected GraphUpdated event to be published")
	}
	publishedType := pub.published[len(pub.published)-1].Type
	if publishedType != EventGraphUpdated {
		t.Errorf("expected event type %q, got %q", EventGraphUpdated, publishedType)
	}

	// Verify at least one component was upserted.
	if len(mc.upsertedItems) == 0 {
		t.Error("expected at least one upserted item")
	}
}

func TestHandle_MissingTenantID(t *testing.T) {
	h := NewGraphBuilderHandler(&mockCosmos{readItems: map[string]map[string]any{}}, &mockPublisher{})
	err := h.Handle(context.Background(), map[string]any{"projectId": "p1", "artifactId": "a1"})
	if err == nil {
		t.Fatal("expected error for missing tenantId")
	}
	we, ok := err.(*WorkerError)
	if !ok || we.IsTransient() {
		t.Error("expected permanent WorkerError")
	}
}

func TestHandleFailure_PublishesEvent(t *testing.T) {
	tenantID := "tenant1"
	artifactID := "artifact1"

	mc := &mockCosmos{
		readItems: map[string]map[string]any{
			DatabaseName + "/" + ProjectsContainer + "/" + artifactID + "/" + tenantID: {
				"id":     artifactID,
				"status": "graph_building",
				"_etag":  `"etag1"`,
			},
		},
	}
	pub := &mockPublisher{}
	h := NewGraphBuilderHandler(mc, pub)

	h.HandleFailure(context.Background(), map[string]any{
		"tenantId":   tenantID,
		"projectId":  "project1",
		"artifactId": artifactID,
	}, "something went wrong")

	if len(pub.published) == 0 {
		t.Fatal("expected GraphBuildFailed event to be published")
	}
	if pub.published[0].Type != EventGraphBuildFailed {
		t.Errorf("expected %q, got %q", EventGraphBuildFailed, pub.published[0].Type)
	}
}

func TestHandleFailure_SkipsUpdateWhenAlreadyPostGraph(t *testing.T) {
	tenantID := "tenant1"
	artifactID := "artifact1"

	mc := &mockCosmos{
		readItems: map[string]map[string]any{
			DatabaseName + "/" + ProjectsContainer + "/" + artifactID + "/" + tenantID: {
				"id":     artifactID,
				"status": "graph_built",
			},
		},
	}
	pub := &mockPublisher{}
	h := NewGraphBuilderHandler(mc, pub)

	h.HandleFailure(context.Background(), map[string]any{
		"tenantId":   tenantID,
		"projectId":  "project1",
		"artifactId": artifactID,
	}, "too late")

	// Should still publish the event.
	if len(pub.published) == 0 {
		t.Fatal("expected GraphBuildFailed event to be published")
	}
	// Should NOT have replaced the document (status already past graph building).
	if len(mc.replacedItems) > 0 {
		t.Error("expected no replace calls when status is already post-graph")
	}
}
