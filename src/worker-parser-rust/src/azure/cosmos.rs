//! Azure Cosmos DB async client.
//!
//! Provides read/write operations for the projects container using the
//! Cosmos DB REST API with managed identity authentication.

use std::time::Duration;

use reqwest::Client;
use serde_json::Value;

use super::credential::ManagedIdentityCredential;

/// Cosmos DB REST API version.
const API_VERSION: &str = "2018-12-31";

/// Cosmos DB resource scope for token acquisition.
const COSMOS_RESOURCE: &str = "https://cosmos.azure.com/";

/// HTTP request timeout for Cosmos DB operations.
const REQUEST_TIMEOUT: Duration = Duration::from_secs(30);

/// Async wrapper around Azure Cosmos DB REST API.
#[derive(Clone)]
pub struct CosmosService {
    client: Client,
    credential: ManagedIdentityCredential,
    endpoint: String,
}

impl CosmosService {
    pub fn new(endpoint: String, credential: ManagedIdentityCredential) -> Self {
        Self {
            client: Client::builder()
                .timeout(REQUEST_TIMEOUT)
                .build()
                .expect("failed to build HTTP client"),
            credential,
            endpoint: endpoint.trim_end_matches('/').to_owned(),
        }
    }

    /// Read a single document by ID and partition key.
    pub async fn read_item(
        &self,
        database: &str,
        container: &str,
        id: &str,
        partition_key: &str,
    ) -> Result<Option<Value>, CosmosError> {
        let token = self.get_token().await?;
        let url = format!(
            "{}/dbs/{database}/colls/{container}/docs/{id}",
            self.endpoint
        );

        let resp = self
            .client
            .get(&url)
            .header("Authorization", format!("type=aad&ver=1.0&sig={token}"))
            .header("x-ms-version", API_VERSION)
            .header("x-ms-documentdb-partitionkey", format!("[\"{partition_key}\"]"))
            .send()
            .await
            .map_err(|e| CosmosError::Request(e.to_string()))?;

        if resp.status().as_u16() == 404 {
            return Ok(None);
        }
        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(CosmosError::Request(format!("HTTP {status}: {body}")));
        }

        let doc: Value = resp
            .json()
            .await
            .map_err(|e| CosmosError::Request(e.to_string()))?;
        Ok(Some(doc))
    }

    /// Create a new document in the specified database/container.
    pub async fn create_item(
        &self,
        database: &str,
        container: &str,
        partition_key: &str,
        document: &Value,
    ) -> Result<Value, CosmosError> {
        let token = self.get_token().await?;
        let url = format!(
            "{}/dbs/{database}/colls/{container}/docs",
            self.endpoint
        );

        let resp = self
            .client
            .post(&url)
            .header("Authorization", format!("type=aad&ver=1.0&sig={token}"))
            .header("x-ms-version", API_VERSION)
            .header("x-ms-documentdb-partitionkey", format!("[\"{partition_key}\"]"))
            .header("Content-Type", "application/json")
            .json(document)
            .send()
            .await
            .map_err(|e| CosmosError::Request(e.to_string()))?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(CosmosError::Request(format!("HTTP {status}: {body}")));
        }

        resp.json()
            .await
            .map_err(|e| CosmosError::Request(e.to_string()))
    }

    /// Replace (upsert) an existing document.
    pub async fn replace_item(
        &self,
        database: &str,
        container: &str,
        id: &str,
        partition_key: &str,
        document: &Value,
        etag: Option<&str>,
    ) -> Result<Value, CosmosError> {
        let token = self.get_token().await?;
        let url = format!(
            "{}/dbs/{database}/colls/{container}/docs/{id}",
            self.endpoint
        );

        let mut req = self
            .client
            .put(&url)
            .header("Authorization", format!("type=aad&ver=1.0&sig={token}"))
            .header("x-ms-version", API_VERSION)
            .header("x-ms-documentdb-partitionkey", format!("[\"{partition_key}\"]"))
            .header("Content-Type", "application/json");

        if let Some(etag_val) = etag {
            req = req
                .header("If-Match", etag_val);
        }

        let resp = req
            .json(document)
            .send()
            .await
            .map_err(|e| CosmosError::Request(e.to_string()))?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(CosmosError::Request(format!("HTTP {status}: {body}")));
        }

        resp.json()
            .await
            .map_err(|e| CosmosError::Request(e.to_string()))
    }

    async fn get_token(&self) -> Result<String, CosmosError> {
        self.credential
            .get_token(COSMOS_RESOURCE)
            .await
            .map_err(|e| CosmosError::Auth(e.to_string()))
    }
}

#[derive(Debug, thiserror::Error)]
pub enum CosmosError {
    #[error("authentication error: {0}")]
    Auth(String),
    #[error("cosmos request failed: {0}")]
    Request(String),
}
