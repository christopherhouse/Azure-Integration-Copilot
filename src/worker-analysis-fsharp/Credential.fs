/// Azure credential factory — mirrors Python shared/credential.py.
module IntegrisightWorkerAnalysis.Credential

open Azure.Identity

/// Create a DefaultAzureCredential.
/// When AZURE_CLIENT_ID is set (user-assigned managed identity), scope to that identity.
let createCredential (clientId: string) : DefaultAzureCredential =
    if System.String.IsNullOrEmpty clientId then
        DefaultAzureCredential()
    else
        DefaultAzureCredential(DefaultAzureCredentialOptions(ManagedIdentityClientId = clientId))
