/// Analysis event handler — processes AnalysisRequested events.
///
/// Mirrors Python workers/analysis/handler.py.
module IntegrisightWorkerAnalysis.AnalysisHandler

open System
open System.Collections.Generic
open System.Text.Json
open Microsoft.Extensions.Logging
open Models
open JsonHelpers
open CosmosRepository
open EventGridClient
open Tools
open AgentOrchestrator

// ---------------------------------------------------------------------------
// Worker error hierarchy
// ---------------------------------------------------------------------------

exception TransientError of string
exception PermanentError of string


// ---------------------------------------------------------------------------
// Handler
// ---------------------------------------------------------------------------

type AnalysisHandler
    (
        analysisRepo: AnalysisRepository,
        eventPublisher: EventGridPublisher,
        orchestrator: AgentOrchestrator,
        logger: ILogger
    ) =

    let acceptedEventType = EventTypes.AnalysisRequested

    member _.AcceptedEventType = acceptedEventType

    /// Return true if the analysis is already completed or failed (idempotency check).
    member _.IsAlreadyProcessedAsync(eventData: JsonElement) =
        task {
            let tenantId =
                match tryGetProp "tenantId" eventData with
                | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                | _ -> ""
            let projectId =
                match tryGetProp "projectId" eventData with
                | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                | _ -> ""
            let analysisId =
                match tryGetProp "analysisId" eventData with
                | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                | _ -> ""
            let pk = $"{tenantId}:{projectId}"

            let! analysisOpt = analysisRepo.GetByIdAsync(pk, analysisId)

            return
                match analysisOpt with
                | None -> false
                | Some a -> a.Status = Completed || a.Status = Failed
        }

    /// Process the AnalysisRequested event — run the agent flow and update Cosmos DB.
    member _.HandleAsync(eventData: JsonElement) =
        task {
            let getString name =
                match tryGetProp name eventData with
                | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                | _ -> ""

            let tenantId = getString "tenantId"
            let projectId = getString "projectId"
            let analysisId = getString "analysisId"
            let prompt = getString "prompt"
            let pk = $"{tenantId}:{projectId}"

            logger.LogInformation(
                "analysis_handler_started tenant_id={TenantId} project_id={ProjectId} analysis_id={AnalysisId}",
                tenantId, projectId, analysisId
            )

            // Load analysis document
            let! analysisOpt = analysisRepo.GetByIdAsync(pk, analysisId)
            let analysis =
                match analysisOpt with
                | None -> raise (PermanentError $"Analysis {analysisId} not found")
                | Some a -> a

            // Transition to running
            let runningAnalysis = { analysis with Status = Running }
            do! analysisRepo.UpsertAsync(runningAnalysis)

            // Set scoping context for tool invocations
            use _ = setContext { TenantId = tenantId; ProjectId = projectId }

            try
                // Run the agent analysis flow
                let! result = orchestrator.RunAnalysisAsync(prompt)

                // Update analysis with result
                let completedAnalysis =
                    { runningAnalysis with
                        Status = Completed
                        Result = Some result
                        CompletedAt = Some DateTimeOffset.UtcNow
                    }
                do! analysisRepo.UpsertAsync(completedAnalysis)

                // Publish AnalysisCompleted event
                let verdictStr =
                    match result.Evaluation with
                    | Some e -> EvaluationVerdict.toString e.Verdict
                    | None -> "UNKNOWN"

                let data = Dictionary<string, obj>()
                data["tenantId"] <- tenantId
                data["projectId"] <- projectId
                data["analysisId"] <- analysisId
                data["verdict"] <- verdictStr

                do!
                    eventPublisher.PublishAsync(
                        EventTypes.AnalysisCompleted,
                        "/integration-copilot/worker/analysis",
                        $"tenants/{tenantId}/projects/{projectId}/analyses/{analysisId}",
                        data
                    )

                logger.LogInformation(
                    "analysis_completed analysis_id={AnalysisId} verdict={Verdict} retry_count={RetryCount} tool_calls={ToolCalls}",
                    analysisId, verdictStr, result.RetryCount, result.ToolCalls.Length
                )

            with ex ->
                logger.LogError(ex, "analysis_failed analysis_id={AnalysisId}", analysisId)
                raise (TransientError $"Analysis failed: {ex.Message}")
        }

    /// Transition analysis to failed and publish AnalysisFailed event.
    member _.HandleFailureAsync(eventData: JsonElement, error: exn) =
        task {
            let getString name =
                match tryGetProp name eventData with
                | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                | _ -> ""

            let tenantId = getString "tenantId"
            let projectId = getString "projectId"
            let analysisId = getString "analysisId"
            let pk = $"{tenantId}:{projectId}"

            try
                let! analysisOpt = analysisRepo.GetByIdAsync(pk, analysisId)
                match analysisOpt with
                | Some analysis ->
                    let failedAnalysis =
                        { analysis with
                            Status = Failed
                            Error = Some(error.Message)
                            CompletedAt = Some DateTimeOffset.UtcNow
                        }
                    do! analysisRepo.UpsertAsync(failedAnalysis)
                | None -> ()

                let data = Dictionary<string, obj>()
                data["tenantId"] <- tenantId
                data["projectId"] <- projectId
                data["analysisId"] <- analysisId
                data["error"] <- error.Message

                do!
                    eventPublisher.PublishAsync(
                        EventTypes.AnalysisFailed,
                        "/integration-copilot/worker/analysis",
                        $"tenants/{tenantId}/projects/{projectId}/analyses/{analysisId}",
                        data
                    )

            with ex ->
                logger.LogError(ex, "handle_failure_error analysis_id={AnalysisId}", analysisId)
        }
