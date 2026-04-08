// Package graph provides deterministic ID generation for graph components and edges.
// The output is byte-for-byte identical to the Python reference implementation.
package graph

import (
	"crypto/sha256"
	"fmt"
)

// GenerateComponentID produces a deterministic stable ID for a graph component.
// Mirrors Python: f"cmp_{hashlib.sha256(key.encode()).hexdigest()[:20]}"
func GenerateComponentID(tenantID, projectID, componentType, canonicalName string) string {
	key := fmt.Sprintf("%s:%s:%s:%s", tenantID, projectID, componentType, canonicalName)
	sum := sha256.Sum256([]byte(key))
	hex := fmt.Sprintf("%x", sum)
	return "cmp_" + hex[:20]
}

// GenerateEdgeID produces a deterministic stable ID for a graph edge.
// Mirrors Python: f"edg_{hashlib.sha256(key.encode()).hexdigest()[:20]}"
func GenerateEdgeID(sourceID, targetID, edgeType string) string {
	key := fmt.Sprintf("%s:%s:%s", sourceID, targetID, edgeType)
	sum := sha256.Sum256([]byte(key))
	hex := fmt.Sprintf("%x", sum)
	return "edg_" + hex[:20]
}
