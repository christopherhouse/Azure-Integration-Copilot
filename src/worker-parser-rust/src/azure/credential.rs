//! Managed identity credential provider.
//!
//! Acquires OAuth2 access tokens from the Azure Instance Metadata Service (IMDS)
//! or the Container App managed identity endpoint, caching them until near-expiry.

use std::sync::Arc;
use std::time::{Duration, Instant};

use reqwest::Client;
use serde::Deserialize;
use tokio::sync::Mutex;

/// Default resource scope for Azure management / data-plane operations.
const DEFAULT_RESOURCE: &str = "https://management.azure.com/";

/// How many seconds before actual expiry we consider the token stale.
const EXPIRY_BUFFER_SECS: u64 = 120;

/// An access token with its expiration time.
#[derive(Debug, Clone)]
pub struct AccessToken {
    pub token: String,
    pub expires_at: Instant,
}

/// Acquires tokens via Azure Managed Identity (IMDS or Container Apps).
#[derive(Clone)]
pub struct ManagedIdentityCredential {
    client: Client,
    client_id: Option<String>,
    cache: Arc<Mutex<Option<AccessToken>>>,
}

#[derive(Deserialize)]
struct ImdsTokenResponse {
    access_token: String,
    expires_in: String,
}

impl ManagedIdentityCredential {
    /// Create a new credential.  If `client_id` is non-empty it will be passed
    /// as the `client_id` query parameter (user-assigned managed identity).
    pub fn new(client_id: Option<String>) -> Self {
        Self {
            client: Client::new(),
            client_id: client_id.filter(|s| !s.is_empty()),
            cache: Arc::new(Mutex::new(None)),
        }
    }

    /// Get a valid access token for the given `resource`, refreshing if needed.
    pub async fn get_token(&self, resource: &str) -> Result<String, CredentialError> {
        {
            let guard = self.cache.lock().await;
            if let Some(ref tok) = *guard
                && Instant::now() < tok.expires_at
            {
                return Ok(tok.token.clone());
            }
        }
        let tok = self.acquire_token(resource).await?;
        let token_str = tok.token.clone();
        {
            let mut guard = self.cache.lock().await;
            *guard = Some(tok);
        }
        Ok(token_str)
    }

    /// Get a valid access token for the default management resource.
    pub async fn get_default_token(&self) -> Result<String, CredentialError> {
        self.get_token(DEFAULT_RESOURCE).await
    }

    async fn acquire_token(&self, resource: &str) -> Result<AccessToken, CredentialError> {
        // Try Container Apps managed identity endpoint first, fall back to IMDS.
        let identity_endpoint = std::env::var("IDENTITY_ENDPOINT").ok();
        let identity_header = std::env::var("IDENTITY_HEADER").ok();

        let resp = if let (Some(endpoint), Some(header)) = (identity_endpoint, identity_header) {
            // Container Apps / App Service managed identity
            let mut url = format!("{endpoint}?api-version=2019-08-01&resource={resource}");
            if let Some(ref cid) = self.client_id {
                url.push_str(&format!("&client_id={cid}"));
            }
            self.client
                .get(&url)
                .header("X-IDENTITY-HEADER", header)
                .send()
                .await
                .map_err(|e| CredentialError::Request(e.to_string()))?
        } else {
            // IMDS endpoint (VM, VMSS, etc.)
            let mut url = format!(
                "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource={resource}"
            );
            if let Some(ref cid) = self.client_id {
                url.push_str(&format!("&client_id={cid}"));
            }
            self.client
                .get(&url)
                .header("Metadata", "true")
                .send()
                .await
                .map_err(|e| CredentialError::Request(e.to_string()))?
        };

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(CredentialError::TokenAcquisition(format!(
                "HTTP {status}: {body}"
            )));
        }

        let body: ImdsTokenResponse = resp
            .json()
            .await
            .map_err(|e| CredentialError::TokenAcquisition(e.to_string()))?;

        let expires_in: u64 = body.expires_in.parse().unwrap_or(3600);
        let expires_at =
            Instant::now() + Duration::from_secs(expires_in.saturating_sub(EXPIRY_BUFFER_SECS));

        Ok(AccessToken {
            token: body.access_token,
            expires_at,
        })
    }
}

/// Credential errors.
#[derive(Debug, thiserror::Error)]
pub enum CredentialError {
    #[error("HTTP request failed: {0}")]
    Request(String),
    #[error("token acquisition failed: {0}")]
    TokenAcquisition(String),
}
