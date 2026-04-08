/// Analysis worker entry point — mirrors Python workers/analysis/main.py.
///
/// Pulls AnalysisRequested events from the analysis-execution subscription
/// and runs the AI agent analysis flow.
module IntegrisightWorkerAnalysis.Program

open System
open System.Runtime.InteropServices
open System.Threading
open Azure.Monitor.OpenTelemetry.Exporter
open Microsoft.Extensions.Logging
open OpenTelemetry
open OpenTelemetry.Resources
open OpenTelemetry.Trace
open CosmosRepository
open EventGridClient
open Tools
open AgentOrchestrator
open AnalysisHandler
open Telemetry
open Worker

[<Literal>]
let SubscriptionName = "analysis-execution"

/// Configure OpenTelemetry tracing with optional Azure Monitor export.
let private setupTelemetry (settings: Config.Settings) =
    let resourceBuilder =
        ResourceBuilder
            .CreateDefault()
            .AddService(ServiceName, serviceVersion = "0.1.0")

    let builder =
        Sdk.CreateTracerProviderBuilder()
            .SetResourceBuilder(resourceBuilder)
            .AddSource(ServiceName)
            .AddHttpClientInstrumentation()

    let builder =
        if not (String.IsNullOrEmpty settings.ApplicationInsightsConnectionString) then
            builder.AddAzureMonitorTraceExporter(fun opts ->
                opts.ConnectionString <- settings.ApplicationInsightsConnectionString)
        else
            builder

    builder.Build()

/// Configure structured console logging.
let private createLogger (name: string) : ILogger =
    let factory =
        LoggerFactory.Create(fun builder ->
            builder
                .AddConsole()
                .SetMinimumLevel(LogLevel.Information)
            |> ignore)
    factory.CreateLogger(name)

[<EntryPoint>]
let main _ =
    let settings = Config.load ()
    use _ = setupTelemetry settings

    let logger = createLogger ServiceName

    logger.LogInformation(
        "analysis_worker_starting subscription={Subscription} environment={Environment}",
        SubscriptionName, settings.Environment
    )

    // Validate required configuration
    if String.IsNullOrEmpty settings.FoundryProjectEndpoint then
        logger.LogError("FOUNDRY_PROJECT_ENDPOINT is required")
        1
    elif String.IsNullOrEmpty settings.CosmosDbEndpoint then
        logger.LogError("COSMOS_DB_ENDPOINT is required")
        1
    elif String.IsNullOrEmpty settings.EventGridNamespaceEndpoint then
        logger.LogError("EVENT_GRID_NAMESPACE_ENDPOINT is required")
        1
    else
        let credential = Credential.createCredential settings.AzureClientId

        // Cosmos DB
        let cosmosProvider = CosmosClientProvider(settings.CosmosDbEndpoint, credential)
        let analysisRepo = AnalysisRepository(cosmosProvider)
        let graphRepo = GraphRepository(cosmosProvider)

        // Event Grid consumer and publisher
        let consumer =
            EventGridConsumer(
                settings.EventGridNamespaceEndpoint,
                settings.EventGridTopic,
                SubscriptionName,
                credential,
                logger
            )

        let publisher =
            EventGridPublisher(
                settings.EventGridNamespaceEndpoint,
                settings.EventGridTopic,
                credential,
                logger
            )

        // Agent tools wired to graph repository
        let toolDefs = buildToolDefinitions graphRepo

        // Agent orchestrator
        let orchestrator = AgentOrchestrator(settings, toolDefs, logger)

        // Analysis event handler
        let handler = AnalysisHandler(analysisRepo, publisher, orchestrator, logger)

        // Base worker
        let worker = BaseWorker(consumer, handler, logger)

        // Graceful shutdown on SIGTERM / SIGINT
        use cts = new CancellationTokenSource()

        let handleShutdown (_: PosixSignalContext) =
            logger.LogInformation("shutdown_signal_received")
            worker.Stop()
            cts.Cancel()

        use _ = PosixSignalRegistration.Create(PosixSignal.SIGTERM, handleShutdown)
        use _ = PosixSignalRegistration.Create(PosixSignal.SIGINT, handleShutdown)

        worker.RunAsync(cts.Token).GetAwaiter().GetResult()

        task {
            do! orchestrator.CloseAsync()
        }
        |> fun t -> t.GetAwaiter().GetResult()

        logger.LogInformation("analysis_worker_stopped")
        0
