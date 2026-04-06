//! Azure Blob Storage async client.
//!
//! Provides download capability for artifact blobs using the Blob Storage
//! REST API with managed identity authentication.

use std::time::Duration;

use reqwest::Client;

use super::credential::ManagedIdentityCredential;

/// The blob storage container name for artifacts.
const ARTIFACTS_CONTAINER: &str = "artifacts";

/// Blob Storage REST API version.
const API_VERSION: &str = "2023-11-03";

/// Storage resource scope for token acquisition.
const STORAGE_RESOURCE: &str = "https://storage.azure.com/";

/// HTTP request timeout for blob operations.
const REQUEST_TIMEOUT: Duration = Duration::from_secs(60);

/// Async wrapper around Azure Blob Storage REST API.
#[derive(Clone)]
pub struct BlobService {
    client: Client,
    credential: ManagedIdentityCredential,
    account_url: String,
}

impl BlobService {
    pub fn new(account_url: String, credential: ManagedIdentityCredential) -> Self {
        Self {
            client: Client::builder()
                .timeout(REQUEST_TIMEOUT)
                .build()
                .expect("failed to build HTTP client"),
            credential,
            account_url: account_url.trim_end_matches('/').to_owned(),
        }
    }

    /// Download the full contents of a blob from the artifacts container.
    pub async fn download_blob(&self, blob_path: &str) -> Result<Vec<u8>, BlobError> {
        let token = self
            .credential
            .get_token(STORAGE_RESOURCE)
            .await
            .map_err(|e| BlobError::Auth(e.to_string()))?;

        let url = format!(
            "{}/{ARTIFACTS_CONTAINER}/{blob_path}",
            self.account_url
        );

        let resp = self
            .client
            .get(&url)
            .header("Authorization", format!("Bearer {token}"))
            .header("x-ms-version", API_VERSION)
            .send()
            .await
            .map_err(|e| BlobError::Request(e.to_string()))?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(BlobError::Request(format!("HTTP {status}: {body}")));
        }

        resp.bytes()
            .await
            .map(|b| b.to_vec())
            .map_err(|e| BlobError::Request(e.to_string()))
    }
}

#[derive(Debug, thiserror::Error)]
pub enum BlobError {
    #[error("authentication error: {0}")]
    Auth(String),
    #[error("blob request failed: {0}")]
    Request(String),
}
