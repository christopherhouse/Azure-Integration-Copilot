from azure.identity.aio import DefaultAzureCredential

from config import settings


def create_credential() -> DefaultAzureCredential:
    """Create an async ``DefaultAzureCredential``.

    When ``AZURE_CLIENT_ID`` is set (i.e. running in Azure with a
    user-assigned managed identity), the credential is scoped to that
    identity.  When the value is empty (local development), plain
    ``DefaultAzureCredential()`` is returned so the Azure CLI / VS Code
    login flow works automatically.
    """
    if settings.azure_client_id:
        return DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id)
    return DefaultAzureCredential()
