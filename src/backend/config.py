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

    # Auth settings
    skip_auth: bool = False
    b2c_tenant_name: str = ""
    b2c_policy_name: str = "B2C_1_signupsignin"
    b2c_client_id: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
