//! Event Grid Namespace pull-delivery consumer.
//!
//! Mirrors the Python `shared/event_consumer.py` — receives, acknowledges, and
//! releases events from an Event Grid Namespace subscription using the REST API.

use std::time::Duration;

use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::azure::credential::ManagedIdentityCredential;

/// Event Grid resource scope for token acquisition.
const EVENTGRID_RESOURCE: &str = "https://eventgrid.azure.net/";

/// Event Grid Namespace API version.
const API_VERSION: &str = "2024-06-01";

/// HTTP request timeout for Event Grid operations.
const REQUEST_TIMEOUT: Duration = Duration::from_secs(60);

/// A single received event with its broker metadata.
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ReceiveDetails {
    pub broker_properties: BrokerProperties,
    pub event: CloudEvent,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BrokerProperties {
    pub lock_token: String,
}

/// CloudEvents v1.0 envelope — just the fields we need.
#[derive(Debug, Clone, Deserialize)]
pub struct CloudEvent {
    pub id: String,
    #[serde(rename = "type")]
    pub event_type: String,
    pub source: String,
    #[serde(default)]
    pub subject: Option<String>,
    #[serde(default)]
    pub data: Option<Value>,
}

#[derive(Deserialize)]
struct ReceiveResponse {
    details: Vec<ReceiveDetails>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct LockTokensBody {
    lock_tokens: Vec<String>,
}

/// Async Event Grid Namespace pull-delivery consumer.
#[derive(Clone)]
pub struct EventGridConsumer {
    client: Client,
    credential: ManagedIdentityCredential,
    endpoint: String,
    topic: String,
    subscription: String,
}

impl EventGridConsumer {
    pub fn new(
        endpoint: String,
        topic: String,
        subscription: String,
        credential: ManagedIdentityCredential,
    ) -> Self {
        Self {
            client: Client::builder()
                .timeout(REQUEST_TIMEOUT)
                .build()
                .expect("failed to build HTTP client"),
            credential,
            endpoint: endpoint.trim_end_matches('/').to_owned(),
            topic,
            subscription,
        }
    }

    /// Pull a batch of events from the subscription.
    pub async fn receive_events(
        &self,
        max_events: u32,
        max_wait_time_secs: u32,
    ) -> Result<Vec<ReceiveDetails>, EventGridConsumerError> {
        let token = self.get_token().await?;
        let url = format!(
            "{}/topics/{}/eventsubscriptions/{}:receive?api-version={API_VERSION}&maxEvents={max_events}&maxWaitTime={max_wait_time_secs}",
            self.endpoint, self.topic, self.subscription
        );

        let resp = self
            .client
            .post(&url)
            .header("Authorization", format!("Bearer {token}"))
            .header("Content-Type", "application/json")
            .body("{}")
            .send()
            .await
            .map_err(|e| EventGridConsumerError::Request(e.to_string()))?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(EventGridConsumerError::Request(format!(
                "receive HTTP {status}: {body}"
            )));
        }

        let body: ReceiveResponse = resp
            .json()
            .await
            .map_err(|e| EventGridConsumerError::Request(e.to_string()))?;

        Ok(body.details)
    }

    /// Acknowledge events so they are removed from the subscription.
    pub async fn acknowledge(
        &self,
        lock_tokens: Vec<String>,
    ) -> Result<(), EventGridConsumerError> {
        if lock_tokens.is_empty() {
            return Ok(());
        }
        self.lock_token_action("acknowledge", lock_tokens).await
    }

    /// Release events back to the subscription for redelivery.
    pub async fn release(
        &self,
        lock_tokens: Vec<String>,
    ) -> Result<(), EventGridConsumerError> {
        if lock_tokens.is_empty() {
            return Ok(());
        }
        self.lock_token_action("release", lock_tokens).await
    }

    async fn lock_token_action(
        &self,
        action: &str,
        lock_tokens: Vec<String>,
    ) -> Result<(), EventGridConsumerError> {
        let token = self.get_token().await?;
        let url = format!(
            "{}/topics/{}/eventsubscriptions/{}:{action}?api-version={API_VERSION}",
            self.endpoint, self.topic, self.subscription
        );

        let body = LockTokensBody { lock_tokens };
        let resp = self
            .client
            .post(&url)
            .header("Authorization", format!("Bearer {token}"))
            .header("Content-Type", "application/json")
            .json(&body)
            .send()
            .await
            .map_err(|e| EventGridConsumerError::Request(e.to_string()))?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body_text = resp.text().await.unwrap_or_default();
            tracing::warn!(
                action,
                status = %status,
                "{action} partial failure: {body_text}"
            );
        }

        Ok(())
    }

    async fn get_token(&self) -> Result<String, EventGridConsumerError> {
        self.credential
            .get_token(EVENTGRID_RESOURCE)
            .await
            .map_err(|e| EventGridConsumerError::Auth(e.to_string()))
    }
}

#[derive(Debug, thiserror::Error)]
pub enum EventGridConsumerError {
    #[error("authentication error: {0}")]
    Auth(String),
    #[error("event grid request failed: {0}")]
    Request(String),
}
