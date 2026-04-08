/// Domain models for the analysis worker.
///
/// These mirror the Python Pydantic models in domains/analysis/models.py and
/// domains/graph/models.py. JSON property names follow the same camelCase
/// convention used in Cosmos DB documents.
module IntegrisightWorkerAnalysis.Models

open System
open System.Text.Json
open System.Text.Json.Serialization
open JsonHelpers

// ---------------------------------------------------------------------------
// Analysis domain
// ---------------------------------------------------------------------------

/// Status values stored in Cosmos DB as lowercase strings.
[<Struct>]
type AnalysisStatus =
    | Pending
    | Running
    | Completed
    | Failed

module AnalysisStatus =
    let toString =
        function
        | Pending -> "pending"
        | Running -> "running"
        | Completed -> "completed"
        | Failed -> "failed"

    let ofString =
        function
        | "pending" -> Pending
        | "running" -> Running
        | "completed" -> Completed
        | "failed" -> Failed
        | s -> failwithf "Unknown AnalysisStatus: %s" s


/// Evaluator verdict stored as uppercase strings.
[<Struct>]
type EvaluationVerdict =
    | Passed
    | EvalFailed

module EvaluationVerdict =
    let toString =
        function
        | Passed -> "PASSED"
        | EvalFailed -> "FAILED"

    let ofString =
        function
        | "PASSED" -> Passed
        | "FAILED" -> EvalFailed
        | s -> failwithf "Unknown EvaluationVerdict: %s" s


/// Record of a single tool call made during analysis.
type ToolCallRecord =
    {
        ToolName: string
        Arguments: JsonElement
        Output: string option
    }

/// Result from the quality evaluator agent.
type EvaluationResult =
    {
        Verdict: EvaluationVerdict
        Confidence: float
        Issues: string list
        Summary: string
    }

/// Full result produced by the agent analysis flow.
type AnalysisResult =
    {
        Response: string
        ToolCalls: ToolCallRecord list
        Evaluation: EvaluationResult option
        RetryCount: int
    }

/// Analysis document stored in the Cosmos DB ``analyses`` container.
/// Property names match the JSON schema used by the Python backend.
type Analysis =
    {
        Id: string
        PartitionKey: string
        Type: string
        TenantId: string
        ProjectId: string
        Prompt: string
        Status: AnalysisStatus
        Result: AnalysisResult option
        Error: string option
        RequestedBy: string
        CreatedAt: DateTimeOffset
        CompletedAt: DateTimeOffset option
    }

// ---------------------------------------------------------------------------
// Graph domain (used by agent tools)
// ---------------------------------------------------------------------------

type Component =
    {
        Id: string
        PartitionKey: string
        Type: string
        TenantId: string
        ProjectId: string
        ArtifactId: string
        ComponentType: string
        Name: string
        DisplayName: string
        Properties: JsonElement
        Tags: string list
        GraphVersion: int
    }

type Edge =
    {
        Id: string
        PartitionKey: string
        Type: string
        TenantId: string
        ProjectId: string
        SourceComponentId: string
        TargetComponentId: string
        EdgeType: string
        ArtifactId: string
        GraphVersion: int
    }

type GraphSummary =
    {
        Id: string
        PartitionKey: string
        Type: string
        TenantId: string
        ProjectId: string
        GraphVersion: int
        TotalComponents: int
        TotalEdges: int
        ComponentCounts: JsonElement
        EdgeCounts: JsonElement
    }

// ---------------------------------------------------------------------------
// JSON serialization helpers
// ---------------------------------------------------------------------------

/// Common JsonSerializerOptions used for Cosmos DB document round-trips.
let cosmosJsonOptions =
    let opts = JsonSerializerOptions()
    opts.PropertyNamingPolicy <- JsonNamingPolicy.CamelCase
    opts.DefaultIgnoreCondition <- JsonIgnoreCondition.WhenWritingNull
    opts

/// Parse an Analysis document from a Cosmos DB JSON string.
let analysisOfJson (json: string) : Analysis =
    let doc = JsonDocument.Parse(json)
    let root = doc.RootElement

    let getString name =
        match tryGetProp name root with
        | true, el -> el.GetString() |> Option.ofObj |> Option.defaultValue ""
        | _ -> ""

    let getStringOpt name =
        match tryGetProp name root with
        | true, el when el.ValueKind <> JsonValueKind.Null -> el.GetString() |> Option.ofObj
        | _ -> None

    let getDateTimeOffset name =
        match tryGetProp name root with
        | true, el when el.ValueKind = JsonValueKind.String ->
            let s : string = el.GetString()
            match DateTimeOffset.TryParse(s : string) with
            | true, dt -> dt
            | _ -> DateTimeOffset.UtcNow
        | _ -> DateTimeOffset.UtcNow

    let getDateTimeOffsetOpt name =
        match tryGetProp name root with
        | true, el when el.ValueKind = JsonValueKind.String ->
            let s : string = el.GetString()
            match DateTimeOffset.TryParse(s : string) with
            | true, dt -> Some dt
            | _ -> None
        | _ -> None

    let parseToolCalls (el: JsonElement) : ToolCallRecord list =
        if el.ValueKind <> JsonValueKind.Array then []
        else
            [ for item in el.EnumerateArray() do
                let toolName =
                    match tryGetProp "toolName" item with
                    | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                    | _ -> ""
                let arguments =
                    match tryGetProp "arguments" item with
                    | true, v -> v
                    | _ -> JsonDocument.Parse("{}").RootElement
                let output =
                    match tryGetProp "output" item with
                    | true, v when v.ValueKind <> JsonValueKind.Null -> v.GetString() |> Option.ofObj
                    | _ -> None
                yield { ToolName = toolName; Arguments = arguments; Output = output } ]

    let parseEvaluation (el: JsonElement) : EvaluationResult option =
        if el.ValueKind = JsonValueKind.Null || el.ValueKind = JsonValueKind.Undefined then None
        else
            let verdict =
                match tryGetProp "verdict" el with
                | true, v -> EvaluationVerdict.ofString (v.GetString())
                | _ -> Passed
            let confidence =
                match tryGetProp "confidence" el with
                | true, v -> v.GetDouble()
                | _ -> 0.0
            let issues =
                match tryGetProp "issues" el with
                | true, v when v.ValueKind = JsonValueKind.Array ->
                    [ for i in v.EnumerateArray() -> i.GetString() |> Option.ofObj |> Option.defaultValue "" ]
                | _ -> []
            let summary =
                match tryGetProp "summary" el with
                | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                | _ -> ""
            Some { Verdict = verdict; Confidence = confidence; Issues = issues; Summary = summary }

    let parseResult (el: JsonElement) : AnalysisResult option =
        if el.ValueKind = JsonValueKind.Null || el.ValueKind = JsonValueKind.Undefined then None
        else
            let response =
                match tryGetProp "response" el with
                | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                | _ -> ""
            let toolCalls =
                match tryGetProp "toolCalls" el with
                | true, v -> parseToolCalls v
                | _ -> []
            let evaluation =
                match tryGetProp "evaluation" el with
                | true, v -> parseEvaluation v
                | _ -> None
            let retryCount =
                match tryGetProp "retryCount" el with
                | true, v -> v.GetInt32()
                | _ -> 0
            Some { Response = response; ToolCalls = toolCalls; Evaluation = evaluation; RetryCount = retryCount }

    let resultEl =
        match tryGetProp "result" root with
        | true, v -> parseResult v
        | _ -> None

    {
        Id = getString "id"
        PartitionKey = getString "partitionKey"
        Type = getString "type"
        TenantId = getString "tenantId"
        ProjectId = getString "projectId"
        Prompt = getString "prompt"
        Status = getString "status" |> AnalysisStatus.ofString
        Result = resultEl
        Error = getStringOpt "error"
        RequestedBy = getString "requestedBy"
        CreatedAt = getDateTimeOffset "createdAt"
        CompletedAt = getDateTimeOffsetOpt "completedAt"
    }

/// Serialize an Analysis to a JSON object (as a Dictionary) for Cosmos DB upsert.
let analysisToDict (analysis: Analysis) : System.Collections.Generic.Dictionary<string, obj> =
    let d = System.Collections.Generic.Dictionary<string, obj>()
    d["id"] <- analysis.Id
    d["partitionKey"] <- analysis.PartitionKey
    d["type"] <- analysis.Type
    d["tenantId"] <- analysis.TenantId
    d["projectId"] <- analysis.ProjectId
    d["prompt"] <- analysis.Prompt
    d["status"] <- AnalysisStatus.toString analysis.Status
    d["requestedBy"] <- analysis.RequestedBy
    d["createdAt"] <- analysis.CreatedAt.ToString("O")

    match analysis.CompletedAt with
    | Some dt -> d["completedAt"] <- dt.ToString("O")
    | None -> d["completedAt"] <- (null : obj)

    match analysis.Error with
    | Some err -> d["error"] <- err
    | None -> d["error"] <- (null : obj)

    match analysis.Result with
    | None -> d["result"] <- (null : obj)
    | Some r ->
        let toolCallsList =
            r.ToolCalls
            |> List.map (fun tc ->
                let tcd = System.Collections.Generic.Dictionary<string, obj>()
                tcd["toolName"] <- tc.ToolName
                tcd["arguments"] <- JsonSerializer.Deserialize<obj>(tc.Arguments.GetRawText())
                match tc.Output with
                | Some o -> tcd["output"] <- o
                | None -> tcd["output"] <- (null : obj)
                tcd :> obj)

        let resultDict = System.Collections.Generic.Dictionary<string, obj>()
        resultDict["response"] <- r.Response
        resultDict["toolCalls"] <- toolCallsList
        resultDict["retryCount"] <- r.RetryCount

        match r.Evaluation with
        | None -> resultDict["evaluation"] <- (null : obj)
        | Some e ->
            let evalDict = System.Collections.Generic.Dictionary<string, obj>()
            evalDict["verdict"] <- EvaluationVerdict.toString e.Verdict
            evalDict["confidence"] <- e.Confidence
            evalDict["issues"] <- e.Issues |> List.toArray
            evalDict["summary"] <- e.Summary
            resultDict["evaluation"] <- evalDict

        d["result"] <- resultDict

    d

/// Parse a Component from a Cosmos DB JSON element.
let componentOfElement (el: JsonElement) : Component =
    let g name =
        match tryGetProp name el with
        | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
        | _ -> ""
    let gInt name =
        match tryGetProp name el with
        | true, v -> v.GetInt32()
        | _ -> 0
    let gEl name =
        match tryGetProp name el with
        | true, v -> v
        | _ -> JsonDocument.Parse("{}").RootElement
    let tags =
        match tryGetProp "tags" el with
        | true, v when v.ValueKind = JsonValueKind.Array ->
            [ for t in v.EnumerateArray() -> t.GetString() |> Option.ofObj |> Option.defaultValue "" ]
        | _ -> []
    {
        Id = g "id"
        PartitionKey = g "partitionKey"
        Type = g "type"
        TenantId = g "tenantId"
        ProjectId = g "projectId"
        ArtifactId = g "artifactId"
        ComponentType = g "componentType"
        Name = g "name"
        DisplayName = g "displayName"
        Properties = gEl "properties"
        Tags = tags
        GraphVersion = gInt "graphVersion"
    }

/// Parse an Edge from a Cosmos DB JSON element.
let edgeOfElement (el: JsonElement) : Edge =
    let g name =
        match tryGetProp name el with
        | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
        | _ -> ""
    let gInt name =
        match tryGetProp name el with
        | true, v -> v.GetInt32()
        | _ -> 0
    {
        Id = g "id"
        PartitionKey = g "partitionKey"
        Type = g "type"
        TenantId = g "tenantId"
        ProjectId = g "projectId"
        SourceComponentId = g "sourceComponentId"
        TargetComponentId = g "targetComponentId"
        EdgeType = g "edgeType"
        ArtifactId = g "artifactId"
        GraphVersion = gInt "graphVersion"
    }

/// Parse a GraphSummary from a Cosmos DB JSON element.
let graphSummaryOfElement (el: JsonElement) : GraphSummary =
    let g name =
        match tryGetProp name el with
        | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
        | _ -> ""
    let gInt name =
        match tryGetProp name el with
        | true, v -> v.GetInt32()
        | _ -> 0
    let gEl name =
        match tryGetProp name el with
        | true, v -> v
        | _ -> JsonDocument.Parse("{}").RootElement
    {
        Id = g "id"
        PartitionKey = g "partitionKey"
        Type = g "type"
        TenantId = g "tenantId"
        ProjectId = g "projectId"
        GraphVersion = gInt "graphVersion"
        TotalComponents = gInt "totalComponents"
        TotalEdges = gInt "totalEdges"
        ComponentCounts = gEl "componentCounts"
        EdgeCounts = gEl "edgeCounts"
    }
