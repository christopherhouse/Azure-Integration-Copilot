// Package eventgrid provides Event Grid Namespace pull-delivery consumer and publisher.
package eventgrid

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"time"

	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/azure/credential"
)

const (
	eventGridResource   = "https://eventgrid.azure.net/"
	apiVersion          = "2024-06-01"
	consumerTimeout     = 60 * time.Second
)

// CloudEvent is a received CloudEvents v1.0 envelope.
type CloudEvent struct {
	ID         string            `json:"id"`
	Type       string            `json:"type"`
	Source     string            `json:"source"`
	Subject    string            `json:"subject,omitempty"`
	Data       json.RawMessage   `json:"data,omitempty"`
	Extensions map[string]any    `json:"extensions,omitempty"`
}

// BrokerProperties contains Event Grid broker metadata for a received event.
type BrokerProperties struct {
	LockToken string `json:"lockToken"`
}

// ReceiveDetails bundles a CloudEvent with its broker metadata.
type ReceiveDetails struct {
	BrokerProperties BrokerProperties `json:"brokerProperties"`
	Event            CloudEvent       `json:"event"`
}

type receiveResponse struct {
	Details []ReceiveDetails `json:"details"`
}

type lockTokensBody struct {
	LockTokens []string `json:"lockTokens"`
}

// EventGridConsumer pulls events from an Event Grid Namespace subscription.
type EventGridConsumer struct {
	client       *http.Client
	credential   *credential.ManagedIdentityCredential
	endpoint     string
	topic        string
	subscription string
}

// NewConsumer creates an EventGridConsumer.
func NewConsumer(endpoint, topic, subscription string, cred *credential.ManagedIdentityCredential) *EventGridConsumer {
	return &EventGridConsumer{
		client:       &http.Client{Timeout: consumerTimeout},
		credential:   cred,
		endpoint:     trimSlash(endpoint),
		topic:        topic,
		subscription: subscription,
	}
}

// ReceiveEvents pulls up to maxEvents events, waiting up to maxWaitSecs seconds.
func (c *EventGridConsumer) ReceiveEvents(ctx context.Context, maxEvents, maxWaitSecs int) ([]ReceiveDetails, error) {
	token, err := c.getToken()
	if err != nil {
		return nil, err
	}

	url := fmt.Sprintf(
		"%s/topics/%s/eventsubscriptions/%s:receive?api-version=%s&maxEvents=%d&maxWaitTime=%d",
		c.endpoint, c.topic, c.subscription, apiVersion, maxEvents, maxWaitSecs,
	)

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewBufferString("{}"))
	if err != nil {
		return nil, fmt.Errorf("build receive request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("receive request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("receive HTTP %d: %s", resp.StatusCode, body)
	}

	var rr receiveResponse
	if err := json.NewDecoder(resp.Body).Decode(&rr); err != nil {
		return nil, fmt.Errorf("decode receive response: %w", err)
	}
	return rr.Details, nil
}

// Acknowledge removes the given events from the subscription.
func (c *EventGridConsumer) Acknowledge(ctx context.Context, lockTokens []string) error {
	if len(lockTokens) == 0 {
		return nil
	}
	return c.lockTokenAction(ctx, "acknowledge", lockTokens)
}

// Release returns the events to the subscription for redelivery.
func (c *EventGridConsumer) Release(ctx context.Context, lockTokens []string) error {
	if len(lockTokens) == 0 {
		return nil
	}
	return c.lockTokenAction(ctx, "release", lockTokens)
}

func (c *EventGridConsumer) lockTokenAction(ctx context.Context, action string, lockTokens []string) error {
	token, err := c.getToken()
	if err != nil {
		return err
	}

	url := fmt.Sprintf(
		"%s/topics/%s/eventsubscriptions/%s:%s?api-version=%s",
		c.endpoint, c.topic, c.subscription, action, apiVersion,
	)

	body := lockTokensBody{LockTokens: lockTokens}
	bodyBytes, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("marshal lock tokens: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(bodyBytes))
	if err != nil {
		return fmt.Errorf("build %s request: %w", action, err)
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return fmt.Errorf("%s request: %w", action, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		// Non-fatal: partial failures are best-effort; log and continue.
		slog.Warn("eventgrid_lock_token_action_partial_failure",
			"action", action,
			"status", resp.StatusCode,
			"body", string(respBody),
		)
	}
	return nil
}

func (c *EventGridConsumer) getToken() (string, error) {
	tok, err := c.credential.GetToken(eventGridResource)
	if err != nil {
		return "", fmt.Errorf("eventgrid consumer auth: %w", err)
	}
	return tok, nil
}

func trimSlash(s string) string {
	for len(s) > 0 && s[len(s)-1] == '/' {
		s = s[:len(s)-1]
	}
	return s
}
