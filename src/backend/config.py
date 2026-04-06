from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    environment: str = "development"
    cosmos_db_endpoint: str = ""
    blob_storage_endpoint: str = ""
    event_grid_namespace_endpoint: str = ""
    event_grid_topic: str = "integration-events"
    web_pubsub_endpoint: str = ""
    azure_client_id: str = ""
    applicationinsights_connection_string: str = ""
    defender_scan_enabled: bool = False

    # CORS settings
    cors_allowed_origins: str = ""

    # Auth settings (Microsoft Entra External ID / CIAM)
    skip_auth: bool = False
    entra_ciam_tenant_subdomain: str = ""
    entra_ciam_client_id: str = ""

    # Security anomaly detection thresholds
    security_auth_failure_threshold: int = 10
    security_auth_failure_window_seconds: int = 300
    security_quota_burst_threshold: int = 10
    security_quota_burst_window_seconds: int = 300

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
