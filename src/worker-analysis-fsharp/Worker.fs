/// Base worker pull loop — mirrors Python workers/base.py.
///
/// Pulls events from Event Grid Namespace, validates them, performs idempotency
/// checks, dispatches to the handler, and handles transient/permanent errors.
module IntegrisightWorkerAnalysis.Worker

open System
open System.Threading
open System.Text.Json
open Microsoft.Extensions.Logging
open EventGridClient
open JsonHelpers
open AnalysisHandler

/// Process a single received event: validate → idempotency → dispatch → acknowledge/release.
let private processEvent
    (consumer: EventGridConsumer)
    (handler: AnalysisHandler)
    (logger: ILogger)
    (detail: ReceivedEventDetail)
    =
    task {
        let lockToken = detail.LockToken
        let eventId = detail.EventId
        let eventType = detail.EventType
        let eventData = detail.Data

        let tenantId =
            match (eventData.TryGetProperty("tenantId") : bool * JsonElement) with
            | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
            | _ -> ""

        // --- Tenant validation ---
        if String.IsNullOrEmpty tenantId then
            logger.LogError(
                "missing_tenant_id event_id={EventId} event_type={EventType}",
                eventId, eventType
            )
            do! consumer.AcknowledgeAsync([ lockToken ])

        // --- Event type validation ---
        elif eventType <> handler.AcceptedEventType then
            logger.LogWarning(
                "unexpected_event_type event_id={EventId} event_type={EventType} accepted={Accepted}",
                eventId, eventType, handler.AcceptedEventType
            )
            do! consumer.AcknowledgeAsync([ lockToken ])

        else
            // --- Idempotency check ---
            let! alreadyProcessed =
                try
                    handler.IsAlreadyProcessedAsync(eventData)
                with ex ->
                    logger.LogError(ex, "idempotency_check_failed event_id={EventId}", eventId)
                    Threading.Tasks.Task.FromResult(false)

            if alreadyProcessed then
                logger.LogInformation("event_already_processed event_id={EventId}", eventId)
                do! consumer.AcknowledgeAsync([ lockToken ])

            else
                // --- Process ---
                try
                    logger.LogInformation("event_processing_started event_id={EventId}", eventId)
                    do! handler.HandleAsync(eventData)
                    do! consumer.AcknowledgeAsync([ lockToken ])
                    logger.LogInformation("event_processing_succeeded event_id={EventId}", eventId)

                with
                | TransientError msg ->
                    logger.LogWarning("transient_error event_id={EventId} message={Message}", eventId, msg)
                    do! consumer.ReleaseAsync([ lockToken ])

                | PermanentError msg ->
                    logger.LogError("permanent_error event_id={EventId} message={Message}", eventId, msg)
                    try
                        do! handler.HandleFailureAsync(eventData, exn msg)
                    with ex ->
                        logger.LogError(ex, "handle_failure_callback_error event_id={EventId}", eventId)
                    do! consumer.AcknowledgeAsync([ lockToken ])

                | ex ->
                    logger.LogError(ex, "unexpected_error event_id={EventId}", eventId)
                    do! consumer.ReleaseAsync([ lockToken ])
    }


type BaseWorker
    (
        consumer: EventGridConsumer,
        handler: AnalysisHandler,
        logger: ILogger,
        ?pollIntervalSeconds: float
    ) =

    let pollInterval = TimeSpan.FromSeconds(defaultArg pollIntervalSeconds 5.0)
    let mutable running = true

    member _.Stop() =
        logger.LogInformation("worker_stop_requested")
        running <- false

    member _.RunAsync(?cancellationToken: CancellationToken) =
        task {
            let ct = defaultArg cancellationToken CancellationToken.None
            let mutable iteration = 0
            logger.LogInformation("worker_started handler={Handler}", nameof AnalysisHandler)

            try
                while running && not ct.IsCancellationRequested do
                    iteration <- iteration + 1

                    try
                        let! details = consumer.ReceiveAsync()

                        if details.IsEmpty then
                            logger.LogDebug("poll_empty iteration={Iteration}", iteration)
                            do! Threading.Tasks.Task.Delay(pollInterval, ct)
                        else
                            logger.LogInformation(
                                "poll_received iteration={Iteration} message_count={Count}",
                                iteration, details.Length
                            )

                            for detail in details do
                                do! processEvent consumer handler logger detail

                    with
                    | :? OperationCanceledException when ct.IsCancellationRequested ->
                        running <- false
                    | ex ->
                        logger.LogError(ex, "receive_events_failed")
                        do! Threading.Tasks.Task.Delay(pollInterval, ct)

            with :? OperationCanceledException ->
                logger.LogInformation("worker_cancelled")

            logger.LogInformation(
                "worker_stopped handler={Handler} total_iterations={Iterations}",
                nameof AnalysisHandler, iteration
            )
        }
