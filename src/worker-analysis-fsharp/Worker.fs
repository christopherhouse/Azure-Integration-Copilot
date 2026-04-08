/// Base worker pull loop — mirrors Python workers/base.py.
///
/// Pulls events from Event Grid Namespace, validates them, performs idempotency
/// checks, dispatches to the handler, and handles transient/permanent errors.
///
/// Distributed Tracing:
/// If a received CloudEvent contains W3C Trace Context extension attributes
/// (``traceparent`` / ``tracestate``), they are extracted and used as the
/// parent context for the ``worker_process_event`` span, maintaining end-to-end
/// correlation across the event-driven pipeline — mirroring the Python worker's
/// ``extract`` + ``tracer.start_as_current_span`` pattern.
module IntegrisightWorkerAnalysis.Worker

open System
open System.Diagnostics
open System.Threading
open Microsoft.Extensions.Logging
open EventGridClient
open JsonHelpers
open AnalysisHandler
open Telemetry

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
            match tryGetProp "tenantId" eventData with
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
            // --- Resolve parent Activity context from CloudEvent trace extensions ---
            // Mirrors Python: carrier = {k: v for k, v in event.extensions.items() if k in ("traceparent", "tracestate")}
            //                 parent_ctx = extract(carrier)
            let traceParent = detail.TraceParent |> Option.defaultValue ""
            let traceState  = detail.TraceState  |> Option.toObj

            let mutable parentCtx = ActivityContext()
            let hasParent =
                traceParent <> ""
                && ActivityContext.TryParse(traceParent, traceState, isRemote = true, context = &parentCtx)

            // Start a processing span, parented to the API request span when available.
            let activityOpt =
                (if hasParent then
                     workerSource.StartActivity("worker_process_event", ActivityKind.Consumer, parentCtx)
                 else
                     workerSource.StartActivity("worker_process_event", ActivityKind.Consumer))
                |> Option.ofObj

            activityOpt
            |> Option.iter (fun a ->
                a.SetTag("worker.event.id",   eventId)   |> ignore
                a.SetTag("worker.event.type", eventType) |> ignore
                a.SetTag("worker.tenant.id",  tenantId)  |> ignore)

            try
                // --- Idempotency check ---
                // On failure, release so the event can be retried rather than
                // proceeding with an unknown state.  Mirrors Python's behaviour.
                try
                    let! alreadyProcessed = handler.IsAlreadyProcessedAsync(eventData)

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

                        | PermanentError msg as permEx ->
                            // Pass the original exception (not a reconstructed one) so that
                            // HandleFailureAsync and telemetry have accurate type/stack info.
                            logger.LogError("permanent_error event_id={EventId} message={Message}", eventId, msg)
                            try
                                do! handler.HandleFailureAsync(eventData, permEx)
                            with ex ->
                                logger.LogError(ex, "handle_failure_callback_error event_id={EventId}", eventId)
                            do! consumer.AcknowledgeAsync([ lockToken ])

                        | ex ->
                            logger.LogError(ex, "unexpected_error event_id={EventId}", eventId)
                            do! consumer.ReleaseAsync([ lockToken ])

                with ex ->
                    // Idempotency check itself failed — release for retry.
                    logger.LogError(ex, "idempotency_check_failed event_id={EventId}", eventId)
                    do! consumer.ReleaseAsync([ lockToken ])

            finally
                activityOpt |> Option.iter (fun a -> a.Dispose())
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
