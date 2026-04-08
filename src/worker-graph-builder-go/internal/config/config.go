// Package config loads application settings from environment variables.
package config

import "os"

// Settings holds all application configuration loaded from environment variables.
type Settings struct {
	Environment                  string
	CosmosDBEndpoint             string
	EventGridNamespaceEndpoint   string
	EventGridTopic               string
	AzureClientID                string
	OTelExporterOTLPEndpoint     string
	ServiceName                  string
}

// FromEnv loads settings from environment variables with sensible defaults.
func FromEnv() Settings {
	return Settings{
		Environment:                envOr("ENVIRONMENT", "development"),
		CosmosDBEndpoint:           envOr("COSMOS_DB_ENDPOINT", ""),
		EventGridNamespaceEndpoint: envOr("EVENT_GRID_NAMESPACE_ENDPOINT", ""),
		EventGridTopic:             envOr("EVENT_GRID_TOPIC", "integration-events"),
		AzureClientID:              envOr("AZURE_CLIENT_ID", ""),
		OTelExporterOTLPEndpoint:   envOr("OTEL_EXPORTER_OTLP_ENDPOINT", ""),
		ServiceName:                envOr("SERVICE_NAME", "integrisight-worker-graph-builder"),
	}
}

func envOr(key, defaultVal string) string {
	if v, ok := os.LookupEnv(key); ok {
		return v
	}
	return defaultVal
}
