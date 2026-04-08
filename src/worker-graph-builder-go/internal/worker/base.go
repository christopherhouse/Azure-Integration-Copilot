// Package worker provides the base pull-loop worker and handler interface.
package worker

import (
	"context"
	"encoding/json"
	"log/slog"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/metric"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"

	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/azure/eventgrid"
)

// WorkerError classifies processing failures.
type WorkerError struct {
	msg       string
	transient bool
}

func (e *WorkerError) Error() string { return e.msg }

// IsTransient reports whether this error is transient (should be retried).
func (e *WorkerError) IsTransient() bool { return e.transient }

// Transient returns a transient WorkerError; the event lock will be released.
func Transient(msg string) *WorkerError { return &WorkerError{msg: msg, transient: true} }

// Permanent returns a permanent WorkerError; HandleFailure is called then the event is acknowledged.
func Permanent(msg string) *WorkerError { return &WorkerError{msg: msg, transient: false} }

// Consumer abstracts Event Grid pull-delivery operations.
type Consumer interface {
	ReceiveEvents(ctx context.Context, maxEvents, maxWaitSecs int) ([]eventgrid.ReceiveDetails, error)
	Acknowledge(ctx context.Context, lockTokens []string) error
	Release(ctx context.Context, lockTokens []string) error
}

// WorkerHandler is the interface that domain-specific handlers must implement.
type WorkerHandler interface {
	// AcceptedEventTypes returns the set of event types this handler processes.
	// Return nil to accept all types.
	AcceptedEventTypes() map[string]bool

	// IsAlreadyProcessed returns true if the event has already been handled.
	IsAlreadyProcessed(ctx context.Context, eventData map[string]any) (bool, error)

	// Handle processes the event. Return Transient or Permanent errors.
	Handle(ctx context.Context, eventData map[string]any) error

	// HandleFailure is called when a permanent error occurs during Handle.
	HandleFailure(ctx context.Context, eventData map[string]any, errMsg string)
}

// BaseWorker drives the Event Grid pull loop.
type BaseWorker struct {
	consumer     Consumer
	handler      WorkerHandler
	pollInterval time.Duration
	running      chan struct{}

	tracer        trace.Tracer
	meter         metric.Meter
	pollCounter   metric.Int64Counter
	msgReceived   metric.Int64Counter
	msgProcessed  metric.Int64Counter
	msgFailed     metric.Int64Counter
	emptyPolls    metric.Int64Counter
}

// NewBaseWorker creates a BaseWorker with 5-second poll interval.
func NewBaseWorker(consumer Consumer, handler WorkerHandler) *BaseWorker {
	tracer := otel.Tracer("integrisight.worker")
	meter := otel.Meter("integrisight.worker")

	pollCounter, _ := meter.Int64Counter("worker.poll.iterations",
		metric.WithDescription("Total number of poll-loop iterations"))
	msgReceived, _ := meter.Int64Counter("worker.messages.received",
		metric.WithDescription("Total number of messages received from Event Grid"))
	msgProcessed, _ := meter.Int64Counter("worker.messages.processed",
		metric.WithDescription("Total number of messages successfully processed"))
	msgFailed, _ := meter.Int64Counter("worker.messages.failed",
		metric.WithDescription("Total number of messages that failed processing"))
	emptyPolls, _ := meter.Int64Counter("worker.poll.empty",
		metric.WithDescription("Total number of poll iterations that returned no messages"))

	return &BaseWorker{
		consumer:      consumer,
		handler:       handler,
		pollInterval:  5 * time.Second,
		running:       make(chan struct{}),
		tracer:        tracer,
		meter:         meter,
		pollCounter:   pollCounter,
		msgReceived:   msgReceived,
		msgProcessed:  msgProcessed,
		msgFailed:     msgFailed,
		emptyPolls:    emptyPolls,
	}
}

// Run starts the pull loop. Blocks until Stop is called or ctx is cancelled.
func (w *BaseWorker) Run(ctx context.Context) {
	slog.Info("worker_started")
	defer slog.Info("worker_stopped")

	for {
		select {
		case <-w.running:
			return
		case <-ctx.Done():
			return
		default:
		}

		w.pollCounter.Add(ctx, 1)

		pollCtx, pollSpan := w.tracer.Start(ctx, "worker poll")

		details, err := w.consumer.ReceiveEvents(pollCtx, 10, 30)
		if err != nil {
			slog.Error("receive_events_failed", "error", err)
			pollSpan.SetStatus(codes.Error, "receive_events_failed")
			pollSpan.End()
			select {
			case <-w.running:
				return
			case <-time.After(w.pollInterval):
			}
			continue
		}

		pollSpan.SetAttributes(attribute.Int("worker.messages.count", len(details)))

		if len(details) == 0 {
			w.emptyPolls.Add(pollCtx, 1)
			pollSpan.SetStatus(codes.Ok, "")
			pollSpan.End()
			select {
			case <-w.running:
				return
			case <-time.After(w.pollInterval):
			}
			continue
		}

		w.msgReceived.Add(pollCtx, int64(len(details)))
		slog.Info("poll_received", "count", len(details))

		for _, detail := range details {
			w.processEvent(pollCtx, detail)
		}

		pollSpan.SetStatus(codes.Ok, "")
		pollSpan.End()
	}
}

// Stop signals the worker to exit after the current iteration.
func (w *BaseWorker) Stop() {
	slog.Info("worker_stop_requested")
	close(w.running)
}

func (w *BaseWorker) processEvent(ctx context.Context, detail eventgrid.ReceiveDetails) {
	ev := detail.Event
	lockToken := detail.BrokerProperties.LockToken

	// Extract W3C trace context from CloudEvent extensions (traceparent / tracestate).
	carrier := propagation.MapCarrier{}
	for _, key := range []string{"traceparent", "tracestate"} {
		if val, ok := ev.Extensions[key]; ok {
			if s, ok := val.(string); ok {
				carrier[key] = s
			}
		}
	}
	parentCtx := otel.GetTextMapPropagator().Extract(ctx, carrier)

	eventCtx, span := w.tracer.Start(parentCtx, "worker process event",
		trace.WithAttributes(
			attribute.String("worker.event.id", ev.ID),
			attribute.String("worker.event.type", ev.Type),
		),
	)
	defer span.End()

	// Parse event data.
	var eventData map[string]any
	if len(ev.Data) > 0 {
		if err := json.Unmarshal(ev.Data, &eventData); err != nil {
			slog.Error("event_data_parse_failed", "event_id", ev.ID, "error", err)
			span.SetStatus(codes.Error, "event_data_parse_failed")
			_ = w.consumer.Acknowledge(eventCtx, []string{lockToken})
			return
		}
	}
	if eventData == nil {
		eventData = map[string]any{}
	}

	tenantID, _ := eventData["tenantId"].(string)

	// Tenant validation.
	if tenantID == "" {
		slog.Error("missing_tenant_id", "event_id", ev.ID)
		span.SetStatus(codes.Error, "missing_tenant_id")
		_ = w.consumer.Acknowledge(eventCtx, []string{lockToken})
		return
	}

	span.SetAttributes(attribute.String("worker.tenant.id", tenantID))

	// Event type validation.
	if accepted := w.handler.AcceptedEventTypes(); accepted != nil {
		if !accepted[ev.Type] {
			slog.Warn("unexpected_event_type", "event_type", ev.Type)
			span.SetStatus(codes.Ok, "")
			_ = w.consumer.Acknowledge(eventCtx, []string{lockToken})
			return
		}
	}

	// Idempotency check.
	already, err := w.handler.IsAlreadyProcessed(eventCtx, eventData)
	if err != nil {
		slog.Error("idempotency_check_failed", "event_id", ev.ID, "error", err)
		span.SetStatus(codes.Error, "idempotency_check_failed")
		w.msgFailed.Add(eventCtx, 1)
		_ = w.consumer.Release(eventCtx, []string{lockToken})
		return
	}
	if already {
		slog.Info("event_already_processed", "event_id", ev.ID)
		span.SetStatus(codes.Ok, "")
		_ = w.consumer.Acknowledge(eventCtx, []string{lockToken})
		return
	}

	// Process.
	slog.Info("event_processing_started", "event_id", ev.ID, "tenant_id", tenantID)
	if err := w.handler.Handle(eventCtx, eventData); err != nil {
		we, ok := err.(*WorkerError)
		if ok && we.IsTransient() {
			slog.Warn("transient_error", "event_id", ev.ID, "error", err)
			span.SetStatus(codes.Error, "transient_error")
			w.msgFailed.Add(eventCtx, 1)
			_ = w.consumer.Release(eventCtx, []string{lockToken})
			return
		}
		// Permanent (or unexpected) error.
		slog.Error("permanent_error", "event_id", ev.ID, "error", err)
		span.SetStatus(codes.Error, "permanent_error")
		w.msgFailed.Add(eventCtx, 1)
		w.handler.HandleFailure(eventCtx, eventData, err.Error())
		_ = w.consumer.Acknowledge(eventCtx, []string{lockToken})
		return
	}

	_ = w.consumer.Acknowledge(eventCtx, []string{lockToken})
	slog.Info("event_processing_succeeded", "event_id", ev.ID)
	span.SetStatus(codes.Ok, "")
	w.msgProcessed.Add(eventCtx, 1)
}
