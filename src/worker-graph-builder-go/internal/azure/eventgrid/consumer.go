// Package eventgrid wraps the Azure Event Grid Namespace SDK (aznamespaces)
// for pull-delivery event consumption and CloudEvent publishing.
package eventgrid

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore"
	"github.com/Azure/azure-sdk-for-go/sdk/azcore/messaging"
	"github.com/Azure/azure-sdk-for-go/sdk/messaging/eventgrid/aznamespaces"
)

// CloudEvent is a received CloudEvents v1.0 envelope.
// Extensions holds CloudEvent extension attributes (e.g. traceparent/tracestate
// for W3C distributed tracing).
type CloudEvent struct {
	ID         string         `json:"id"`
	Type       string         `json:"type"`
	Source     string         `json:"source"`
	Subject    string         `json:"subject,omitempty"`
	Data       json.RawMessage
	Extensions map[string]any
}

// BrokerProperties contains Event Grid broker metadata for a received event.
type BrokerProperties struct {
	LockToken string
}

// ReceiveDetails bundles a CloudEvent with its broker metadata.
type ReceiveDetails struct {
	BrokerProperties BrokerProperties
	Event            CloudEvent
}

// EventGridConsumer pulls events from an Event Grid Namespace subscription
// using the official Azure SDK (aznamespaces.ReceiverClient).
type EventGridConsumer struct {
	receiver *aznamespaces.ReceiverClient
}

// NewConsumer creates an EventGridConsumer backed by the official aznamespaces SDK.
func NewConsumer(endpoint, topic, subscription string, cred azcore.TokenCredential) (*EventGridConsumer, error) {
	receiver, err := aznamespaces.NewReceiverClient(endpoint, topic, subscription, cred, nil)
	if err != nil {
		return nil, fmt.Errorf("create event grid receiver client: %w", err)
	}
	return &EventGridConsumer{receiver: receiver}, nil
}

// ReceiveEvents pulls up to maxEvents events, waiting up to maxWaitSecs seconds.
func (c *EventGridConsumer) ReceiveEvents(ctx context.Context, maxEvents, maxWaitSecs int) ([]ReceiveDetails, error) {
	maxEventsI32 := int32(maxEvents)
	maxWaitI32 := int32(maxWaitSecs)
	resp, err := c.receiver.ReceiveEvents(ctx, &aznamespaces.ReceiveEventsOptions{
		MaxEvents:   &maxEventsI32,
		MaxWaitTime: &maxWaitI32,
	})
	if err != nil {
		return nil, fmt.Errorf("receive events: %w", err)
	}

	details := make([]ReceiveDetails, 0, len(resp.Details))
	for _, d := range resp.Details {
		details = append(details, mapReceiveDetails(d))
	}
	return details, nil
}

// Acknowledge removes the given events from the subscription.
func (c *EventGridConsumer) Acknowledge(ctx context.Context, lockTokens []string) error {
	if len(lockTokens) == 0 {
		return nil
	}
	_, err := c.receiver.AcknowledgeEvents(ctx, lockTokens, nil)
	if err != nil {
		slog.Warn("eventgrid_acknowledge_partial_failure", "error", err)
	}
	return nil
}

// Release returns the given events to the subscription for redelivery.
func (c *EventGridConsumer) Release(ctx context.Context, lockTokens []string) error {
	if len(lockTokens) == 0 {
		return nil
	}
	_, err := c.receiver.ReleaseEvents(ctx, lockTokens, nil)
	if err != nil {
		slog.Warn("eventgrid_release_partial_failure", "error", err)
	}
	return nil
}

// mapReceiveDetails converts an aznamespaces.ReceiveDetails to our local type.
func mapReceiveDetails(d aznamespaces.ReceiveDetails) ReceiveDetails {
	ce := d.Event
	var lockToken string
	if d.BrokerProperties != nil && d.BrokerProperties.LockToken != nil {
		lockToken = *d.BrokerProperties.LockToken
	}

	// Marshal the CloudEvent data to JSON bytes so base.go can unmarshal it uniformly.
	var dataBytes json.RawMessage
	if ce.Data != nil {
		if b, err := json.Marshal(ce.Data); err == nil {
			dataBytes = b
		}
	}

	var subject string
	if ce.Subject != nil {
		subject = *ce.Subject
	}

	return ReceiveDetails{
		BrokerProperties: BrokerProperties{LockToken: lockToken},
		Event: CloudEvent{
			ID:         ce.ID,
			Type:       ce.Type,
			Source:     ce.Source,
			Subject:    subject,
			Data:       dataBytes,
			Extensions: ce.Extensions,
		},
	}
}

// EventGridPublisher publishes CloudEvents to an Event Grid Namespace topic
// using the official Azure SDK (aznamespaces.SenderClient).
type EventGridPublisher struct {
	sender *aznamespaces.SenderClient
}

// NewPublisher creates an EventGridPublisher backed by the official aznamespaces SDK.
// When endpoint is empty the publisher is a no-op (useful in testing / local dev).
func NewPublisher(endpoint, topic string, cred azcore.TokenCredential) (*EventGridPublisher, error) {
	if endpoint == "" {
		return &EventGridPublisher{}, nil
	}
	sender, err := aznamespaces.NewSenderClient(endpoint, topic, cred, nil)
	if err != nil {
		return nil, fmt.Errorf("create event grid sender client: %w", err)
	}
	return &EventGridPublisher{sender: sender}, nil
}

// CloudEventOut is the outbound CloudEvents v1.0 envelope.
// It wraps messaging.CloudEvent for compatibility with the rest of the codebase.
type CloudEventOut = messaging.CloudEvent

// BuildCloudEvent constructs a CloudEventOut ready for publishing.
// The ID is set to a new UUID; specversion is always "1.0".
func BuildCloudEvent(eventType, source, subject string, data any) CloudEventOut {
	ce, err := messaging.NewCloudEvent(source, eventType, data, &messaging.CloudEventOptions{
		Subject: &subject,
	})
	if err != nil {
		// NewCloudEvent only errors on nil source/type; panic is appropriate here.
		panic(fmt.Sprintf("build cloud event: %v", err))
	}
	return ce
}

// PublishEvent publishes a single CloudEvent. A no-op when no sender is configured.
func (p *EventGridPublisher) PublishEvent(ctx context.Context, event CloudEventOut) error {
	if p.sender == nil {
		slog.Warn("event_grid_not_configured_skipping_publish", "event_type", event.Type)
		return nil
	}
	if _, err := p.sender.SendEvent(ctx, &event, nil); err != nil {
		return fmt.Errorf("publish event %q: %w", event.Type, err)
	}
	slog.Info("event_published", "event_type", event.Type, "subject", event.Subject)
	return nil
}
