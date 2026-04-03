//! Application settings loaded from environment variables.
//!
//! Mirrors the Python `config.py` Settings class.

/// Application settings loaded from environment variables.
#[derive(Debug, Clone)]
pub struct Settings {
    pub environment: String,
    pub cosmos_db_endpoint: String,
    pub blob_storage_endpoint: String,
    pub event_grid_namespace_endpoint: String,
    pub event_grid_topic: String,
    pub azure_client_id: String,
}

impl Settings {
    /// Load settings from environment variables with sensible defaults.
    pub fn from_env() -> Self {
        Self {
            environment: env_or("ENVIRONMENT", "development"),
            cosmos_db_endpoint: env_or("COSMOS_DB_ENDPOINT", ""),
            blob_storage_endpoint: env_or("BLOB_STORAGE_ENDPOINT", ""),
            event_grid_namespace_endpoint: env_or("EVENT_GRID_NAMESPACE_ENDPOINT", ""),
            event_grid_topic: env_or("EVENT_GRID_TOPIC", "integration-events"),
            azure_client_id: env_or("AZURE_CLIENT_ID", ""),
        }
    }
}

fn env_or(key: &str, default: &str) -> String {
    std::env::var(key).unwrap_or_else(|_| default.to_owned())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn settings_has_defaults() {
        let s = Settings::from_env();
        assert_eq!(s.event_grid_topic, "integration-events");
    }
}
