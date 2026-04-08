// Package cosmos wraps the Azure Cosmos DB SDK (azcosmos) for use in the
// graph builder worker.
package cosmos

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sync"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore"
	"github.com/Azure/azure-sdk-for-go/sdk/data/azcosmos"
)

// QueryParam is a named parameter for a Cosmos DB SQL query.
// It is a type alias for azcosmos.QueryParameter so callers do not need to
// import azcosmos directly.
type QueryParam = azcosmos.QueryParameter

// CosmosService wraps the azcosmos client with convenience methods that
// marshal/unmarshal documents as map[string]any.
type CosmosService struct {
	client     *azcosmos.Client
	containers sync.Map // key: "database/container" → *azcosmos.ContainerClient
}

// New creates a CosmosService authenticated via the supplied Azure credential.
func New(endpoint string, cred azcore.TokenCredential) (*CosmosService, error) {
	client, err := azcosmos.NewClient(endpoint, cred, nil)
	if err != nil {
		return nil, fmt.Errorf("create cosmos client: %w", err)
	}
	return &CosmosService{client: client}, nil
}

// containerClient returns a cached *azcosmos.ContainerClient for the given
// database and container pair.
func (s *CosmosService) containerClient(database, container string) (*azcosmos.ContainerClient, error) {
	key := database + "/" + container
	if v, ok := s.containers.Load(key); ok {
		return v.(*azcosmos.ContainerClient), nil
	}
	c, err := s.client.NewContainer(database, container)
	if err != nil {
		return nil, fmt.Errorf("get container client %s/%s: %w", database, container, err)
	}
	s.containers.Store(key, c)
	return c, nil
}

// ReadItem reads a single document by ID. Returns (nil, nil) when not found.
func (s *CosmosService) ReadItem(ctx context.Context, database, container, id, partitionKey string) (map[string]any, error) {
	c, err := s.containerClient(database, container)
	if err != nil {
		return nil, err
	}

	pk := azcosmos.NewPartitionKeyString(partitionKey)
	resp, err := c.ReadItem(ctx, pk, id, nil)
	if err != nil {
		if isNotFound(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("read item %q: %w", id, err)
	}

	var doc map[string]any
	if err := json.Unmarshal(resp.Value, &doc); err != nil {
		return nil, fmt.Errorf("unmarshal item %q: %w", id, err)
	}
	return doc, nil
}

// ReplaceItem replaces an existing document. When etag is non-empty an
// If-Match check is applied for optimistic concurrency control.
func (s *CosmosService) ReplaceItem(ctx context.Context, database, container, id, partitionKey string, document map[string]any, etag string) (map[string]any, error) {
	c, err := s.containerClient(database, container)
	if err != nil {
		return nil, err
	}

	raw, err := json.Marshal(document)
	if err != nil {
		return nil, fmt.Errorf("marshal document for replace: %w", err)
	}

	pk := azcosmos.NewPartitionKeyString(partitionKey)
	opts := &azcosmos.ItemOptions{}
	if etag != "" {
		ev := azcore.ETag(etag)
		opts.IfMatchEtag = &ev
	}

	resp, err := c.ReplaceItem(ctx, pk, id, raw, opts)
	if err != nil {
		return nil, fmt.Errorf("replace item %q: %w", id, err)
	}

	var doc map[string]any
	if err := json.Unmarshal(resp.Value, &doc); err != nil {
		return nil, fmt.Errorf("unmarshal replaced item %q: %w", id, err)
	}
	return doc, nil
}

// UpsertItem inserts or replaces a document.
func (s *CosmosService) UpsertItem(ctx context.Context, database, container, partitionKey string, document map[string]any) (map[string]any, error) {
	c, err := s.containerClient(database, container)
	if err != nil {
		return nil, err
	}

	raw, err := json.Marshal(document)
	if err != nil {
		return nil, fmt.Errorf("marshal document for upsert: %w", err)
	}

	pk := azcosmos.NewPartitionKeyString(partitionKey)
	resp, err := c.UpsertItem(ctx, pk, raw, nil)
	if err != nil {
		return nil, fmt.Errorf("upsert item: %w", err)
	}

	var doc map[string]any
	if err := json.Unmarshal(resp.Value, &doc); err != nil {
		return nil, fmt.Errorf("unmarshal upserted item: %w", err)
	}
	return doc, nil
}

// QueryItems executes a parameterised SQL query, collecting all pages.
// Results are returned as a slice of document maps.
func (s *CosmosService) QueryItems(ctx context.Context, database, container, partitionKey, query string, params []QueryParam) ([]map[string]any, error) {
	c, err := s.containerClient(database, container)
	if err != nil {
		return nil, err
	}

	pk := azcosmos.NewPartitionKeyString(partitionKey)
	opts := &azcosmos.QueryOptions{QueryParameters: params}
	pager := c.NewQueryItemsPager(query, pk, opts)

	var results []map[string]any
	for pager.More() {
		page, err := pager.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("query items page: %w", err)
		}
		for _, raw := range page.Items {
			var doc map[string]any
			if err := json.Unmarshal(raw, &doc); err != nil {
				return nil, fmt.Errorf("unmarshal query result: %w", err)
			}
			results = append(results, doc)
		}
	}
	return results, nil
}

// isNotFound returns true when err represents an HTTP 404 from Cosmos DB.
func isNotFound(err error) bool {
	var re *azcore.ResponseError
	return errors.As(err, &re) && re.StatusCode == 404
}
