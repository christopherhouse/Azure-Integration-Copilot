package config

import (
	"os"
	"testing"
)

func TestDefaults(t *testing.T) {
	// Ensure no env vars interfere
	for _, key := range []string{
		"ENVIRONMENT", "COSMOS_DB_ENDPOINT", "EVENT_GRID_NAMESPACE_ENDPOINT",
		"EVENT_GRID_TOPIC", "AZURE_CLIENT_ID", "OTEL_EXPORTER_OTLP_ENDPOINT", "SERVICE_NAME",
	} {
		os.Unsetenv(key)
	}

	s := FromEnv()

	if s.Environment != "development" {
		t.Errorf("expected environment=development, got %q", s.Environment)
	}
	if s.EventGridTopic != "integration-events" {
		t.Errorf("expected topic=integration-events, got %q", s.EventGridTopic)
	}
	if s.CosmosDBEndpoint != "" {
		t.Errorf("expected empty cosmos endpoint, got %q", s.CosmosDBEndpoint)
	}
	if s.ServiceName != "integrisight-worker-graph-builder" {
		t.Errorf("expected default service name, got %q", s.ServiceName)
	}
}

func TestOverrideViaEnvVar(t *testing.T) {
	os.Setenv("ENVIRONMENT", "production")
	os.Setenv("EVENT_GRID_TOPIC", "my-topic")
	os.Setenv("SERVICE_NAME", "custom-service")
	defer func() {
		os.Unsetenv("ENVIRONMENT")
		os.Unsetenv("EVENT_GRID_TOPIC")
		os.Unsetenv("SERVICE_NAME")
	}()

	s := FromEnv()

	if s.Environment != "production" {
		t.Errorf("expected environment=production, got %q", s.Environment)
	}
	if s.EventGridTopic != "my-topic" {
		t.Errorf("expected topic=my-topic, got %q", s.EventGridTopic)
	}
	if s.ServiceName != "custom-service" {
		t.Errorf("expected service name=custom-service, got %q", s.ServiceName)
	}
}
