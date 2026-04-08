/// Application settings loaded from environment variables.
module IntegrisightWorkerAnalysis.Config

open System

type Settings =
    {
        Environment: string
        CosmosDbEndpoint: string
        EventGridNamespaceEndpoint: string
        EventGridTopic: string
        WebPubSubEndpoint: string
        AzureClientId: string
        ApplicationInsightsConnectionString: string
        FoundryProjectEndpoint: string
        FoundryModelDeploymentName: string
    }

let load () =
    let env key defaultValue =
        let v = Environment.GetEnvironmentVariable key
        if String.IsNullOrEmpty v then defaultValue else v

    {
        Environment = env "ENVIRONMENT" "development"
        CosmosDbEndpoint = env "COSMOS_DB_ENDPOINT" ""
        EventGridNamespaceEndpoint = env "EVENT_GRID_NAMESPACE_ENDPOINT" ""
        EventGridTopic = env "EVENT_GRID_TOPIC" "integration-events"
        WebPubSubEndpoint = env "WEB_PUBSUB_ENDPOINT" ""
        AzureClientId = env "AZURE_CLIENT_ID" ""
        ApplicationInsightsConnectionString = env "APPLICATIONINSIGHTS_CONNECTION_STRING" ""
        FoundryProjectEndpoint = env "FOUNDRY_PROJECT_ENDPOINT" ""
        FoundryModelDeploymentName = env "FOUNDRY_MODEL_DEPLOYMENT_NAME" "gpt-4o"
    }
