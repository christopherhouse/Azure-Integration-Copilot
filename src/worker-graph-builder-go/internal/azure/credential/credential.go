// Package credential provides Azure Managed Identity token acquisition and caching.
package credential

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"sync"
	"time"
)

const (
	expiryBufferSecs   = 120
	tokenRequestTimeout = 30 * time.Second
)

// AccessToken holds a bearer token and its expiry time.
type AccessToken struct {
	Token     string
	ExpiresAt time.Time
}

// ManagedIdentityCredential acquires OAuth2 tokens from Azure Managed Identity.
// It supports Container Apps (IDENTITY_ENDPOINT + IDENTITY_HEADER env vars)
// and falls back to the standard IMDS endpoint.
// Tokens are cached per-resource with a 120-second early-expiry buffer.
type ManagedIdentityCredential struct {
	client   *http.Client
	clientID string
	mu       sync.Mutex
	cache    map[string]AccessToken
}

type imdsTokenResponse struct {
	AccessToken string `json:"access_token"`
	ExpiresIn   string `json:"expires_in"`
}

// New creates a ManagedIdentityCredential. Pass a non-empty clientID for
// user-assigned managed identity; pass "" for system-assigned.
func New(clientID string) *ManagedIdentityCredential {
	return &ManagedIdentityCredential{
		client: &http.Client{
			Timeout: tokenRequestTimeout,
		},
		clientID: clientID,
		cache:    make(map[string]AccessToken),
	}
}

// GetToken returns a valid access token for the given resource scope,
// refreshing from the identity endpoint when the cached token is near-expiry.
func (c *ManagedIdentityCredential) GetToken(resource string) (string, error) {
	c.mu.Lock()
	if tok, ok := c.cache[resource]; ok && time.Now().Before(tok.ExpiresAt) {
		c.mu.Unlock()
		return tok.Token, nil
	}
	c.mu.Unlock()

	tok, err := c.acquireToken(resource)
	if err != nil {
		return "", err
	}

	c.mu.Lock()
	c.cache[resource] = tok
	c.mu.Unlock()

	return tok.Token, nil
}

func (c *ManagedIdentityCredential) acquireToken(resource string) (AccessToken, error) {
	identityEndpoint := os.Getenv("IDENTITY_ENDPOINT")
	identityHeader := os.Getenv("IDENTITY_HEADER")

	var req *http.Request
	var err error

	if identityEndpoint != "" && identityHeader != "" {
		// Container Apps / App Service managed identity
		rawURL := fmt.Sprintf("%s?api-version=2019-08-01&resource=%s", identityEndpoint, resource)
		if c.clientID != "" {
			rawURL += "&client_id=" + c.clientID
		}
		req, err = http.NewRequest(http.MethodGet, rawURL, nil)
		if err != nil {
			return AccessToken{}, fmt.Errorf("build container app token request: %w", err)
		}
		req.Header.Set("X-IDENTITY-HEADER", identityHeader)
	} else {
		// Standard IMDS endpoint
		rawURL := fmt.Sprintf(
			"http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=%s",
			resource,
		)
		if c.clientID != "" {
			rawURL += "&client_id=" + c.clientID
		}
		req, err = http.NewRequest(http.MethodGet, rawURL, nil)
		if err != nil {
			return AccessToken{}, fmt.Errorf("build IMDS token request: %w", err)
		}
		req.Header.Set("Metadata", "true")
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return AccessToken{}, fmt.Errorf("token request failed: %w", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return AccessToken{}, fmt.Errorf("token acquisition failed HTTP %d: %s", resp.StatusCode, body)
	}

	var parsed imdsTokenResponse
	if err := json.Unmarshal(body, &parsed); err != nil {
		return AccessToken{}, fmt.Errorf("parse token response: %w", err)
	}

	var expiresIn int64
	if _, scanErr := fmt.Sscanf(parsed.ExpiresIn, "%d", &expiresIn); scanErr != nil || expiresIn <= 0 {
		expiresIn = 3600
	}

	effectiveSecs := expiresIn - expiryBufferSecs
	if effectiveSecs < 0 {
		effectiveSecs = 0
	}
	expiresAt := time.Now().Add(time.Duration(effectiveSecs) * time.Second)

	return AccessToken{
		Token:     parsed.AccessToken,
		ExpiresAt: expiresAt,
	}, nil
}
