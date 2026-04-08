package eventgrid

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/google/uuid"
)

const publisherTimeout = 30 * time.Second

// CloudEventOut is a CloudEvents v1.0 envelope for publishing.
type CloudEventOut struct {
	ID          string    `json:"id"`
	Type        string    `json:"type"`
	Source      string    `json:"source"`
	Subject     string    `json:"subject,omitempty"`
	Data        any       `json:"data"`
	Time        time.Time `json:"time"`
	SpecVersion string    `json:"specversion"`
}

// BuildCloudEvent constructs a CloudEventOut with a generated ID.
func BuildCloudEvent(eventType, source, subject string, data any) CloudEventOut {
	return CloudEventOut{
		ID:          "evt_" + uuid.New().String(),
		Type:        eventType,
		Source:      source,
		Subject:     subject,
		Data:        data,
		Time:        time.Now().UTC(),
		SpecVersion: "1.0",
	}
}

// EventGridPublisher publishes CloudEvents to an Event Grid Namespace topic.
type EventGridPublisher struct {
	client     *http.Client
	credential interface{ GetToken(string) (string, error) }
	endpoint   string
	topic      string
}

// NewPublisher creates an EventGridPublisher.
func NewPublisher(endpoint, topic string, cred interface{ GetToken(string) (string, error) }) *EventGridPublisher {
	return &EventGridPublisher{
		client:     &http.Client{Timeout: publisherTimeout},
		credential: cred,
		endpoint:   trimSlash(endpoint),
		topic:      topic,
	}
}

// PublishEvent publishes a single CloudEvent. A no-op if the endpoint is empty.
func (p *EventGridPublisher) PublishEvent(ctx context.Context, event CloudEventOut) error {
	if p.endpoint == "" {
		return nil
	}

	token, err := p.credential.GetToken(eventGridResource)
	if err != nil {
		return fmt.Errorf("eventgrid publisher auth: %w", err)
	}

	url := fmt.Sprintf("%s/topics/%s:publish?api-version=%s", p.endpoint, p.topic, apiVersion)

	bodyBytes, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(bodyBytes))
	if err != nil {
		return fmt.Errorf("build publish request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/cloudevents+json; charset=utf-8")

	resp, err := p.client.Do(req)
	if err != nil {
		return fmt.Errorf("publish request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("publish HTTP %d: %s", resp.StatusCode, respBody)
	}
	return nil
}
