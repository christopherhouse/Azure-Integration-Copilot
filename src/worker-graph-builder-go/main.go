// Integrisight.ai — Go graph builder worker.
//
// Pulls ArtifactParsed events from Event Grid Namespace (pull delivery),
// transforms parse results into graph data in Cosmos DB, and publishes
// GraphUpdated or GraphBuildFailed events.
package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetrichttp"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"

	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/azure/cosmos"
	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/azure/credential"
	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/azure/eventgrid"
	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/config"
	"github.com/christopherhouse/integrisight/worker-graph-builder-go/internal/worker"
)

func main() {
	// Structured JSON logging via slog.
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	settings := config.FromEnv()
	slog.Info("worker_initialising",
		"service", settings.ServiceName,
		"environment", settings.Environment,
		"subscription", worker.SubscriptionName,
	)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// OTel setup.
	shutdownOTel := setupOTel(ctx, settings)
	defer shutdownOTel()

	// Managed identity credential (azidentity SDK).
	cred, err := credential.New(settings.AzureClientID)
	if err != nil {
		slog.Error("credential_init_failed", "error", err)
		os.Exit(1)
	}

	// Cosmos DB client (azcosmos SDK).
	cosmosClient, err := cosmos.New(settings.CosmosDBEndpoint, cred)
	if err != nil {
		slog.Error("cosmos_client_init_failed", "error", err)
		os.Exit(1)
	}

	// Event Grid Namespace consumer (aznamespaces SDK).
	consumer, err := eventgrid.NewConsumer(
		settings.EventGridNamespaceEndpoint,
		settings.EventGridTopic,
		worker.SubscriptionName,
		cred,
	)
	if err != nil {
		slog.Error("eventgrid_consumer_init_failed", "error", err)
		os.Exit(1)
	}

	// Event Grid Namespace publisher (aznamespaces SDK).
	publisher, err := eventgrid.NewPublisher(
		settings.EventGridNamespaceEndpoint,
		settings.EventGridTopic,
		cred,
	)
	if err != nil {
		slog.Error("eventgrid_publisher_init_failed", "error", err)
		os.Exit(1)
	}

	// Domain handler.
	handler := worker.NewGraphBuilderHandler(cosmosClient, publisher)

	// Base worker (adapts the concrete consumer to the Consumer interface).
	baseWorker := worker.NewBaseWorker(&consumerAdapter{consumer}, handler)

	// Graceful shutdown on SIGTERM / SIGINT.
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)
	go func() {
		sig := <-sigCh
		slog.Info("shutdown_signal_received", "signal", sig.String())
		baseWorker.Stop()
		cancel()
	}()

	slog.Info("graph_builder_worker_starting", "subscription", worker.SubscriptionName)
	baseWorker.Run(ctx)
}

// consumerAdapter adapts *eventgrid.EventGridConsumer to the worker.Consumer interface.
type consumerAdapter struct {
	c *eventgrid.EventGridConsumer
}

func (a *consumerAdapter) ReceiveEvents(ctx context.Context, maxEvents, maxWaitSecs int) ([]eventgrid.ReceiveDetails, error) {
	return a.c.ReceiveEvents(ctx, maxEvents, maxWaitSecs)
}

func (a *consumerAdapter) Acknowledge(ctx context.Context, lockTokens []string) error {
	return a.c.Acknowledge(ctx, lockTokens)
}

func (a *consumerAdapter) Release(ctx context.Context, lockTokens []string) error {
	return a.c.Release(ctx, lockTokens)
}


// setupOTel configures OTLP tracing and metrics exporters when the endpoint is set.
// Returns a shutdown function.
func setupOTel(ctx context.Context, settings config.Settings) func() {
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	if settings.OTelExporterOTLPEndpoint == "" {
		// No-op: use default no-op providers.
		return func() {}
	}

	// Trace exporter.
	traceExporter, err := otlptracehttp.New(ctx,
		otlptracehttp.WithEndpointURL(settings.OTelExporterOTLPEndpoint),
		otlptracehttp.WithInsecure(),
	)
	if err != nil {
		slog.Warn("otlp_trace_exporter_init_failed", "error", err)
		return func() {}
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)
	otel.SetTracerProvider(tp)

	// Metric exporter.
	metricExporter, err := otlpmetrichttp.New(ctx,
		otlpmetrichttp.WithEndpointURL(settings.OTelExporterOTLPEndpoint),
		otlpmetrichttp.WithInsecure(),
	)
	if err != nil {
		slog.Warn("otlp_metric_exporter_init_failed", "error", err)
		return func() { _ = tp.Shutdown(context.Background()) }
	}

	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExporter)),
	)
	otel.SetMeterProvider(mp)

	return func() {
		_ = tp.Shutdown(context.Background())
		_ = mp.Shutdown(context.Background())
	}
}
