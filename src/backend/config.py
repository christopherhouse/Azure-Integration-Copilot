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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
