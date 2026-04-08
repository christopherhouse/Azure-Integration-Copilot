// Package worker contains the graph builder domain handler.
package worker

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/azure/cosmos"
	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/azure/eventgrid"
	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/graph"
)

// Event type constants.
const (
	EventArtifactParsed   = "com.integration-copilot.artifact.parsed.v1"
	EventGraphUpdated     = "com.integration-copilot.graph.updated.v1"
	EventGraphBuildFailed = "com.integration-copilot.graph.build-failed.v1"
)

// Cosmos DB constants.
const (
	DatabaseName      = "integration-copilot"
	ProjectsContainer = "projects"
	GraphContainer    = "graph"
	SubscriptionName  = "graph-builder"
	EventSourceGraph  = "/integration-copilot/worker/graph-builder"
)

// postGraphStatuses are artifact statuses indicating the artifact has already
// progressed past graph building.
var postGraphStatuses = map[string]bool{
	"graph_built":  true,
	"graph_failed": true,
}

// CosmosClient abstracts Cosmos DB operations (enables testing via mocks).
type CosmosClient interface {
	ReadItem(ctx context.Context, database, container, id, partitionKey string) (map[string]any, error)
	CreateItem(ctx context.Context, database, container, partitionKey string, document map[string]any) (map[string]any, error)
	ReplaceItem(ctx context.Context, database, container, id, partitionKey string, document map[string]any, etag string) (map[string]any, error)
	UpsertItem(ctx context.Context, database, container, partitionKey string, document map[string]any) (map[string]any, error)
	QueryItems(ctx context.Context, database, container, partitionKey, query string, params []cosmos.QueryParam) ([]map[string]any, error)
	ExecuteStoredProcedure(ctx context.Context, database, container, partitionKey, sprocName string, params []any) (map[string]any, error)
}

// Publisher abstracts event publishing (enables testing via mocks).
type Publisher interface {
	PublishEvent(ctx context.Context, event eventgrid.CloudEventOut) error
}

// GraphBuilderHandler processes ArtifactParsed events.
type GraphBuilderHandler struct {
	cosmos    CosmosClient
	publisher Publisher
}

// NewGraphBuilderHandler creates a GraphBuilderHandler.
func NewGraphBuilderHandler(cosmosClient CosmosClient, publisher Publisher) *GraphBuilderHandler {
	return &GraphBuilderHandler{
		cosmos:    cosmosClient,
		publisher: publisher,
	}
}

// AcceptedEventTypes returns the set of event types this handler accepts.
func (h *GraphBuilderHandler) AcceptedEventTypes() map[string]bool {
	return map[string]bool{EventArtifactParsed: true}
}

// IsAlreadyProcessed returns true if the artifact has already been graph-built or failed.
func (h *GraphBuilderHandler) IsAlreadyProcessed(ctx context.Context, eventData map[string]any) (bool, error) {
	tenantID, _ := eventData["tenantId"].(string)
	artifactID, _ := eventData["artifactId"].(string)

	artifact, err := h.cosmos.ReadItem(ctx, DatabaseName, ProjectsContainer, artifactID, tenantID)
	if err != nil {
		return false, fmt.Errorf("read artifact for idempotency: %w", err)
	}
	if artifact == nil {
		return false, nil
	}

	status, _ := artifact["status"].(string)
	return postGraphStatuses[status], nil
}

// Handle processes an ArtifactParsed event end-to-end.
func (h *GraphBuilderHandler) Handle(ctx context.Context, eventData map[string]any) error {
	tenantID, _ := eventData["tenantId"].(string)
	projectID, _ := eventData["projectId"].(string)
	artifactID, _ := eventData["artifactId"].(string)
	parseResultID, _ := eventData["parseResultId"].(string)

	if tenantID == "" {
		return Permanent("missing tenantId")
	}
	if projectID == "" {
		return Permanent("missing projectId")
	}
	if artifactID == "" {
		return Permanent("missing artifactId")
	}

	slog.Info("handle_graph_build", "tenant_id", tenantID, "project_id", projectID, "artifact_id", artifactID)

	// Step 1: Transition artifact → graph_building.
	if err := h.updateArtifactStatus(ctx, tenantID, artifactID, "graph_building"); err != nil {
		return Transient(fmt.Sprintf("failed to transition to graph_building: %v", err))
	}

	// Step 2: Load parse result.
	parseResult, err := h.loadParseResult(ctx, tenantID, parseResultID, artifactID)
	if err != nil {
		return Transient(fmt.Sprintf("failed to load parse result: %v", err))
	}
	if parseResult == nil {
		return Permanent(fmt.Sprintf("parse result not found for artifact %s", artifactID))
	}

	// Step 3: Load project for graphVersion.
	project, err := h.cosmos.ReadItem(ctx, DatabaseName, ProjectsContainer, projectID, tenantID)
	if err != nil {
		return Transient(fmt.Sprintf("failed to read project %s: %v", projectID, err))
	}
	if project == nil {
		return Permanent(fmt.Sprintf("project %s not found for tenant %s", projectID, tenantID))
	}

	currentGraphVersion := toInt64(project["graphVersion"])
	newGraphVersion := currentGraphVersion + 1
	partitionKey := tenantID + ":" + projectID
	now := time.Now().UTC()
	nowStr := now.Format(time.RFC3339)

	// Step 4–6: Build id mapping and process components/edges.
	idMap := make(map[string]string)

	// Process components.
	components := toSlice(parseResult["components"])
	for _, raw := range components {
		comp := toMap(raw)
		if comp == nil {
			continue
		}
		tempID, _ := comp["tempId"].(string)
		componentType, _ := comp["componentType"].(string)
		name, _ := comp["name"].(string)
		displayName, _ := comp["displayName"].(string)
		if displayName == "" {
			displayName = name
		}

		stableID := graph.GenerateComponentID(tenantID, projectID, componentType, name)
		if tempID != "" {
			idMap[tempID] = stableID
		}

		properties := toMapAny(comp["properties"])
		doc := map[string]any{
			"id":            stableID,
			"partitionKey":  partitionKey,
			"type":          "component",
			"tenantId":      tenantID,
			"projectId":     projectID,
			"artifactId":    artifactID,
			"componentType": componentType,
			"name":          name,
			"displayName":   displayName,
			"properties":    properties,
			"tags":          []any{},
			"graphVersion":  newGraphVersion,
			"createdAt":     nowStr,
			"updatedAt":     nowStr,
		}
		if _, err := h.cosmos.UpsertItem(ctx, DatabaseName, GraphContainer, partitionKey, doc); err != nil {
			return Transient(fmt.Sprintf("failed to upsert component %s: %v", stableID, err))
		}
	}

	// Process external references.
	externalRefs := toSlice(parseResult["externalReferences"])
	for _, raw := range externalRefs {
		ref := toMap(raw)
		if ref == nil {
			continue
		}
		tempID, _ := ref["tempId"].(string)
		componentType, _ := ref["componentType"].(string)
		if componentType == "" {
			componentType = "external_service"
		}
		name, _ := ref["name"].(string)
		displayName, _ := ref["displayName"].(string)
		if displayName == "" {
			displayName = name
		}
		inferredFrom, _ := ref["inferredFrom"].(string)

		stableID := graph.GenerateComponentID(tenantID, projectID, componentType, name)
		if tempID != "" {
			idMap[tempID] = stableID
		}

		doc := map[string]any{
			"id":            stableID,
			"partitionKey":  partitionKey,
			"type":          "component",
			"tenantId":      tenantID,
			"projectId":     projectID,
			"artifactId":    artifactID,
			"componentType": componentType,
			"name":          name,
			"displayName":   displayName,
			"properties":    map[string]any{"inferredFrom": inferredFrom},
			"tags":          []any{"external"},
			"graphVersion":  newGraphVersion,
			"createdAt":     nowStr,
			"updatedAt":     nowStr,
		}
		if _, err := h.cosmos.UpsertItem(ctx, DatabaseName, GraphContainer, partitionKey, doc); err != nil {
			return Transient(fmt.Sprintf("failed to upsert external ref %s: %v", stableID, err))
		}
	}

	// Process edges.
	edges := toSlice(parseResult["edges"])
	for _, raw := range edges {
		edge := toMap(raw)
		if edge == nil {
			continue
		}
		sourceTempID, _ := edge["sourceTempId"].(string)
		targetTempID, _ := edge["targetTempId"].(string)
		edgeType, _ := edge["edgeType"].(string)

		sourceID := idMap[sourceTempID]
		if sourceID == "" {
			sourceID = sourceTempID
		}
		targetID := idMap[targetTempID]
		if targetID == "" {
			targetID = targetTempID
		}

		edgeID := graph.GenerateEdgeID(sourceID, targetID, edgeType)
		edgeProps := toMapAny(edge["properties"])

		doc := map[string]any{
			"id":               edgeID,
			"partitionKey":     partitionKey,
			"type":             "edge",
			"tenantId":         tenantID,
			"projectId":        projectID,
			"sourceComponentId": sourceID,
			"targetComponentId": targetID,
			"edgeType":         edgeType,
			"properties":       edgeProps,
			"artifactId":       artifactID,
			"graphVersion":     newGraphVersion,
			"createdAt":        nowStr,
		}
		if _, err := h.cosmos.UpsertItem(ctx, DatabaseName, GraphContainer, partitionKey, doc); err != nil {
			return Transient(fmt.Sprintf("failed to upsert edge %s: %v", edgeID, err))
		}
	}

	// Step 10: Compute graph summary via stored procedure.
	summaryResult, err := h.cosmos.ExecuteStoredProcedure(ctx, DatabaseName, GraphContainer, partitionKey, "graphCountByTypes", nil)
	if err != nil {
		return Transient(fmt.Sprintf("failed to execute graphCountByTypes sproc: %v", err))
	}

	componentCounts := toMapAny(summaryResult["componentCounts"])
	edgeCounts := toMapAny(summaryResult["edgeCounts"])
	totalComponents := toInt64(summaryResult["totalComponents"])
	totalEdges := toInt64(summaryResult["totalEdges"])

	summaryID := "gs_" + partitionKey
	summaryDoc := map[string]any{
		"id":              summaryID,
		"partitionKey":    partitionKey,
		"type":            "graph_summary",
		"tenantId":        tenantID,
		"projectId":       projectID,
		"graphVersion":    newGraphVersion,
		"totalComponents": totalComponents,
		"totalEdges":      totalEdges,
		"componentCounts": componentCounts,
		"edgeCounts":      edgeCounts,
		"updatedAt":       nowStr,
	}
	if _, err := h.cosmos.UpsertItem(ctx, DatabaseName, GraphContainer, partitionKey, summaryDoc); err != nil {
		return Transient(fmt.Sprintf("failed to upsert graph summary: %v", err))
	}

	// Step 11: Increment project graphVersion.
	if err := h.incrementProjectGraphVersion(ctx, tenantID, projectID, newGraphVersion); err != nil {
		return Transient(fmt.Sprintf("failed to increment project graphVersion: %v", err))
	}

	// Step 12: Transition artifact → graph_built.
	if err := h.updateArtifactStatus(ctx, tenantID, artifactID, "graph_built"); err != nil {
		return Transient(fmt.Sprintf("failed to transition to graph_built: %v", err))
	}

	// Step 13: Publish GraphUpdated event.
	event := eventgrid.BuildCloudEvent(
		EventGraphUpdated,
		EventSourceGraph,
		fmt.Sprintf("tenants/%s/projects/%s", tenantID, projectID),
		map[string]any{
			"tenantId":        tenantID,
			"projectId":       projectID,
			"artifactId":      artifactID,
			"graphVersion":    newGraphVersion,
			"totalComponents": totalComponents,
			"totalEdges":      totalEdges,
		},
	)
	if err := h.publisher.PublishEvent(ctx, event); err != nil {
		slog.Warn("graph_updated_event_publish_failed", "error", err)
	}

	slog.Info("graph_built",
		"tenant_id", tenantID,
		"project_id", projectID,
		"graph_version", newGraphVersion,
		"components", totalComponents,
		"edges", totalEdges,
	)
	return nil
}

// HandleFailure transitions the artifact to graph_failed and publishes a GraphBuildFailed event.
func (h *GraphBuilderHandler) HandleFailure(ctx context.Context, eventData map[string]any, errMsg string) {
	tenantID, _ := eventData["tenantId"].(string)
	artifactID, _ := eventData["artifactId"].(string)
	projectID, _ := eventData["projectId"].(string)

	artifact, readErr := h.cosmos.ReadItem(ctx, DatabaseName, ProjectsContainer, artifactID, tenantID)
	if readErr == nil && artifact != nil {
		status, _ := artifact["status"].(string)
		if !postGraphStatuses[status] {
			if err := h.updateArtifactStatus(ctx, tenantID, artifactID, "graph_failed"); err != nil {
				slog.Error("update_status_graph_failed_error", "artifact_id", artifactID, "error", err)
			}
		}
	}

	event := eventgrid.BuildCloudEvent(
		EventGraphBuildFailed,
		EventSourceGraph,
		fmt.Sprintf("tenants/%s/projects/%s/artifacts/%s", tenantID, projectID, artifactID),
		map[string]any{
			"tenantId":   tenantID,
			"projectId":  projectID,
			"artifactId": artifactID,
			"error":      errMsg,
		},
	)
	if err := h.publisher.PublishEvent(ctx, event); err != nil {
		slog.Error("graph_build_failed_event_publish_error", "artifact_id", artifactID, "error", err)
	}
}

// --- Private helpers ---

// updateArtifactStatus performs a read-then-replace with ETag optimistic concurrency.
func (h *GraphBuilderHandler) updateArtifactStatus(ctx context.Context, tenantID, artifactID, newStatus string) error {
	doc, err := h.cosmos.ReadItem(ctx, DatabaseName, ProjectsContainer, artifactID, tenantID)
	if err != nil {
		return fmt.Errorf("read artifact: %w", err)
	}
	if doc == nil {
		return fmt.Errorf("artifact %s not found for tenant %s", artifactID, tenantID)
	}

	etag, _ := doc["_etag"].(string)
	doc["status"] = newStatus
	doc["updatedAt"] = time.Now().UTC().Format(time.RFC3339)

	if _, err := h.cosmos.ReplaceItem(ctx, DatabaseName, ProjectsContainer, artifactID, tenantID, doc, etag); err != nil {
		return fmt.Errorf("replace artifact: %w", err)
	}
	return nil
}

// incrementProjectGraphVersion reads the project and sets graphVersion = newVersion.
func (h *GraphBuilderHandler) incrementProjectGraphVersion(ctx context.Context, tenantID, projectID string, newVersion int64) error {
	doc, err := h.cosmos.ReadItem(ctx, DatabaseName, ProjectsContainer, projectID, tenantID)
	if err != nil {
		return fmt.Errorf("read project: %w", err)
	}
	if doc == nil {
		return fmt.Errorf("project %s not found for tenant %s", projectID, tenantID)
	}

	etag, _ := doc["_etag"].(string)
	doc["graphVersion"] = newVersion
	doc["updatedAt"] = time.Now().UTC().Format(time.RFC3339)

	if _, err := h.cosmos.ReplaceItem(ctx, DatabaseName, ProjectsContainer, projectID, tenantID, doc, etag); err != nil {
		return fmt.Errorf("replace project: %w", err)
	}
	return nil
}

// loadParseResult tries to load by parseResultID first, then falls back to
// querying by artifactID (most recent parse result, ORDER BY parsedAt DESC).
func (h *GraphBuilderHandler) loadParseResult(ctx context.Context, tenantID, parseResultID, artifactID string) (map[string]any, error) {
	if parseResultID != "" {
		doc, err := h.cosmos.ReadItem(ctx, DatabaseName, ProjectsContainer, parseResultID, tenantID)
		if err == nil && doc != nil {
			if docType, _ := doc["type"].(string); docType == "parse_result" {
				return doc, nil
			}
		}
		slog.Warn("parse_result_not_found_by_id", "parse_result_id", parseResultID)
	}

	// Fallback: query by artifactId.
	query := "SELECT * FROM c WHERE c.partitionKey = @tenantId AND c.type = 'parse_result' AND c.artifactId = @artifactId ORDER BY c.parsedAt DESC OFFSET 0 LIMIT 1"
	params := []cosmos.QueryParam{
		{Name: "@tenantId", Value: tenantID},
		{Name: "@artifactId", Value: artifactID},
	}
	docs, err := h.cosmos.QueryItems(ctx, DatabaseName, ProjectsContainer, tenantID, query, params)
	if err != nil {
		return nil, fmt.Errorf("query parse result: %w", err)
	}
	if len(docs) == 0 {
		return nil, nil
	}
	return docs[0], nil
}

// --- JSON coercion helpers ---

func toSlice(v any) []any {
	if v == nil {
		return nil
	}
	s, _ := v.([]any)
	return s
}

func toMap(v any) map[string]any {
	if v == nil {
		return nil
	}
	m, _ := v.(map[string]any)
	return m
}

func toMapAny(v any) map[string]any {
	if m, ok := v.(map[string]any); ok {
		return m
	}
	// Try JSON round-trip for edge cases (e.g. json.Number).
	if v != nil {
		raw, err := json.Marshal(v)
		if err == nil {
			var out map[string]any
			if json.Unmarshal(raw, &out) == nil {
				return out
			}
		}
	}
	return map[string]any{}
}

func toInt64(v any) int64 {
	switch val := v.(type) {
	case int64:
		return val
	case float64:
		return int64(val)
	case json.Number:
		n, _ := val.Int64()
		return n
	case int:
		return int64(val)
	}
	return 0
}
