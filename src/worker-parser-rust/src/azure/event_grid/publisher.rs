//! Event Grid Namespace publisher.
//!
//! Mirrors the Python `shared/events.py` — publishes CloudEvents to an
//! Event Grid Namespace topic using the REST API.

use chrono::{DateTime, Utc};
use reqwest::Client;
use serde::Serialize;
use serde_json::Value;
use ulid::Ulid;

use crate::azure::credential::ManagedIdentityCredential;

/// Event Grid resource scope for token acquisition.
const EVENTGRID_RESOURCE: &str = "https://eventgrid.azure.net/";

/// Event Grid Namespace API version.
const API_VERSION: &str = "2024-06-01";

/// CloudEvents v1.0 envelope for publishing.
#[derive(Debug, Clone, Serialize)]
pub struct CloudEventOut {
    pub id: String,
    #[serde(rename = "type")]
    pub event_type: String,
    pub source: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subject: Option<String>,
    pub data: Value,
    pub time: DateTime<Utc>,
    pub specversion: String,
}

/// Build a CloudEvent for publishing.
pub fn build_cloud_event(
    event_type: &str,
    source: &str,
    subject: &str,
    data: Value,
) -> CloudEventOut {
    CloudEventOut {
        id: format!("evt_{}", Ulid::new()),
        event_type: event_type.to_owned(),
        source: source.to_owned(),
        subject: Some(subject.to_owned()),
        data,
        time: Utc::now(),
        specversion: "1.0".to_owned(),
    }
}

/// Async Event Grid Namespace publisher.
#[derive(Clone)]
pub struct EventGridPublisher {
    client: Client,
    credential: ManagedIdentityCredential,
    endpoint: String,
    topic: String,
}

impl EventGridPublisher {
    pub fn new(
        endpoint: String,
        topic: String,
        credential: ManagedIdentityCredential,
    ) -> Self {
        Self {
            client: Client::new(),
            credential,
            endpoint: endpoint.trim_end_matches('/').to_owned(),
            topic,
        }
    }

    /// Publish a single CloudEvent to the configured topic.
    pub async fn publish_event(
        &self,
        event: &CloudEventOut,
    ) -> Result<(), EventGridPublisherError> {
        if self.endpoint.is_empty() {
            tracing::warn!(event_type = %event.event_type, "event_grid_not_configured");
            return Ok(());
        }

        let token = self.get_token().await?;
        let url = format!(
            "{}/topics/{}:publish?api-version={API_VERSION}",
            self.endpoint, self.topic
        );

        let resp = self
            .client
            .post(&url)
            .header("Authorization", format!("Bearer {token}"))
            .header("Content-Type", "application/cloudevents+json; charset=utf-8")
            .json(event)
            .send()
            .await
            .map_err(|e| EventGridPublisherError::Request(e.to_string()))?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            tracing::warn!(
                event_type = %event.event_type,
                status = %status,
                "event_publish_failed: {body}"
            );
            return Err(EventGridPublisherError::Request(format!(
                "HTTP {status}: {body}"
            )));
        }

        tracing::info!(
            event_type = %event.event_type,
            subject = ?event.subject,
            "event_published"
        );
        Ok(())
    }

    async fn get_token(&self) -> Result<String, EventGridPublisherError> {
        self.credential
            .get_token(EVENTGRID_RESOURCE)
            .await
            .map_err(|e| EventGridPublisherError::Auth(e.to_string()))
    }
}

#[derive(Debug, thiserror::Error)]
pub enum EventGridPublisherError {
    #[error("authentication error: {0}")]
    Auth(String),
    #[error("event grid publish failed: {0}")]
    Request(String),
}
