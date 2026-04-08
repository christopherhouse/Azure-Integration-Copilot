// Package cosmos provides an Azure Cosmos DB REST API client with managed identity auth.
package cosmos

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/azure/credential"
)

const (
	apiVersion      = "2018-12-31"
	cosmosResource  = "https://cosmos.azure.com/"
	requestTimeout  = 30 * time.Second
)

// CosmosService wraps the Cosmos DB REST API with managed identity authentication.
type CosmosService struct {
	client     *http.Client
	credential *credential.ManagedIdentityCredential
	endpoint   string
}

// QueryParam is a named parameter for a Cosmos DB SQL query.
type QueryParam struct {
	Name  string `json:"name"`
	Value any    `json:"value"`
}

// New creates a CosmosService for the given endpoint.
func New(endpoint string, cred *credential.ManagedIdentityCredential) *CosmosService {
	return &CosmosService{
		client:     &http.Client{Timeout: requestTimeout},
		credential: cred,
		endpoint:   trimTrailingSlash(endpoint),
	}
}

// ReadItem reads a single document by ID and partition key.
// Returns (nil, nil) when the document is not found (HTTP 404).
func (s *CosmosService) ReadItem(ctx context.Context, database, container, id, partitionKey string) (map[string]any, error) {
	token, err := s.getToken()
	if err != nil {
		return nil, err
	}

	url := fmt.Sprintf("%s/dbs/%s/colls/%s/docs/%s", s.endpoint, database, container, id)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("build read request: %w", err)
	}
	s.setCommonHeaders(req, token, partitionKey)

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cosmos read request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, nil
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("cosmos read HTTP %d: %s", resp.StatusCode, body)
	}

	var doc map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&doc); err != nil {
		return nil, fmt.Errorf("decode read response: %w", err)
	}
	return doc, nil
}

// CreateItem creates a new document in the specified database/container.
func (s *CosmosService) CreateItem(ctx context.Context, database, container, partitionKey string, document map[string]any) (map[string]any, error) {
	token, err := s.getToken()
	if err != nil {
		return nil, err
	}

	url := fmt.Sprintf("%s/dbs/%s/colls/%s/docs", s.endpoint, database, container)
	body, err := json.Marshal(document)
	if err != nil {
		return nil, fmt.Errorf("marshal document: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("build create request: %w", err)
	}
	s.setCommonHeaders(req, token, partitionKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cosmos create request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("cosmos create HTTP %d: %s", resp.StatusCode, respBody)
	}

	var result map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode create response: %w", err)
	}
	return result, nil
}

// ReplaceItem replaces an existing document. If etag is non-empty, an
// If-Match header is sent for optimistic concurrency.
func (s *CosmosService) ReplaceItem(ctx context.Context, database, container, id, partitionKey string, document map[string]any, etag string) (map[string]any, error) {
	token, err := s.getToken()
	if err != nil {
		return nil, err
	}

	url := fmt.Sprintf("%s/dbs/%s/colls/%s/docs/%s", s.endpoint, database, container, id)
	body, err := json.Marshal(document)
	if err != nil {
		return nil, fmt.Errorf("marshal document: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPut, url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("build replace request: %w", err)
	}
	s.setCommonHeaders(req, token, partitionKey)
	req.Header.Set("Content-Type", "application/json")
	if etag != "" {
		req.Header.Set("If-Match", etag)
	}

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cosmos replace request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("cosmos replace HTTP %d: %s", resp.StatusCode, respBody)
	}

	var result map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode replace response: %w", err)
	}
	return result, nil
}

// UpsertItem upserts a document (POST with x-ms-documentdb-is-upsert: true).
func (s *CosmosService) UpsertItem(ctx context.Context, database, container, partitionKey string, document map[string]any) (map[string]any, error) {
	token, err := s.getToken()
	if err != nil {
		return nil, err
	}

	url := fmt.Sprintf("%s/dbs/%s/colls/%s/docs", s.endpoint, database, container)
	body, err := json.Marshal(document)
	if err != nil {
		return nil, fmt.Errorf("marshal document: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("build upsert request: %w", err)
	}
	s.setCommonHeaders(req, token, partitionKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-ms-documentdb-is-upsert", "true")

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cosmos upsert request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("cosmos upsert HTTP %d: %s", resp.StatusCode, respBody)
	}

	var result map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode upsert response: %w", err)
	}
	return result, nil
}

// QueryItems executes a SQL query against a container, following continuation
// tokens to page through all results.
func (s *CosmosService) QueryItems(ctx context.Context, database, container, partitionKey, query string, params []QueryParam) ([]map[string]any, error) {
	token, err := s.getToken()
	if err != nil {
		return nil, err
	}

	type queryBody struct {
		Query      string       `json:"query"`
		Parameters []QueryParam `json:"parameters"`
	}

	type queryResponse struct {
		Documents []map[string]any `json:"Documents"`
	}

	payload := queryBody{Query: query, Parameters: params}
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("marshal query body: %w", err)
	}

	url := fmt.Sprintf("%s/dbs/%s/colls/%s/docs", s.endpoint, database, container)

	var allDocs []map[string]any
	continuationToken := ""

	for {
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(payloadBytes))
		if err != nil {
			return nil, fmt.Errorf("build query request: %w", err)
		}
		s.setCommonHeaders(req, token, partitionKey)
		req.Header.Set("Content-Type", "application/query+json")
		req.Header.Set("x-ms-documentdb-isquery", "true")
		req.Header.Set("x-ms-documentdb-query-enablecrosspartition", "false")
		if continuationToken != "" {
			req.Header.Set("x-ms-continuation", continuationToken)
		}

		resp, err := s.client.Do(req)
		if err != nil {
			return nil, fmt.Errorf("cosmos query request: %w", err)
		}

		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			respBody, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			return nil, fmt.Errorf("cosmos query HTTP %d: %s", resp.StatusCode, respBody)
		}

		var qr queryResponse
		if err := json.NewDecoder(resp.Body).Decode(&qr); err != nil {
			resp.Body.Close()
			return nil, fmt.Errorf("decode query response: %w", err)
		}
		continuationToken = resp.Header.Get("x-ms-continuation")
		resp.Body.Close()

		allDocs = append(allDocs, qr.Documents...)

		if continuationToken == "" {
			break
		}
	}

	return allDocs, nil
}

// ExecuteStoredProcedure invokes a stored procedure with the given parameters.
// params may be nil or empty; in that case an empty JSON array is sent.
func (s *CosmosService) ExecuteStoredProcedure(ctx context.Context, database, container, partitionKey, sprocName string, params []any) (map[string]any, error) {
	token, err := s.getToken()
	if err != nil {
		return nil, err
	}

	if params == nil {
		params = []any{}
	}
	bodyBytes, err := json.Marshal(params)
	if err != nil {
		return nil, fmt.Errorf("marshal sproc params: %w", err)
	}

	url := fmt.Sprintf("%s/dbs/%s/colls/%s/sprocs/%s", s.endpoint, database, container, sprocName)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, fmt.Errorf("build sproc request: %w", err)
	}
	s.setCommonHeaders(req, token, partitionKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("cosmos sproc request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("cosmos sproc HTTP %d: %s", resp.StatusCode, respBody)
	}

	var result map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode sproc response: %w", err)
	}
	return result, nil
}

func (s *CosmosService) setCommonHeaders(req *http.Request, token, partitionKey string) {
	req.Header.Set("Authorization", fmt.Sprintf("type=aad&ver=1.0&sig=%s", token))
	req.Header.Set("x-ms-version", apiVersion)
	req.Header.Set("x-ms-documentdb-partitionkey", fmt.Sprintf("[\"%s\"]", partitionKey))
}

func (s *CosmosService) getToken() (string, error) {
	tok, err := s.credential.GetToken(cosmosResource)
	if err != nil {
		return "", fmt.Errorf("cosmos auth: %w", err)
	}
	return tok, nil
}

func trimTrailingSlash(s string) string {
	for len(s) > 0 && s[len(s)-1] == '/' {
		s = s[:len(s)-1]
	}
	return s
}
