/// Agent orchestrator — analyst + evaluator using OpenAI Assistants API via Azure AI Foundry.
///
/// Mirrors Python workers/analysis/agent.py.
///
/// The analyst agent uses 4 function tools to query the dependency graph.
/// The evaluator validates the analyst response and returns a JSON verdict.
/// On FAILED verdict, the analyst is re-prompted once (max 1 retry).
module IntegrisightWorkerAnalysis.AgentOrchestrator

#nowarn "57" // OpenAI.Assistants is marked [<Experimental>] in the preview SDK

open System
open System.ClientModel
open System.Collections.Generic
open System.Text.Json
open System.Threading.Tasks
open Azure.AI.OpenAI
open OpenAI.Assistants
open Microsoft.Extensions.Logging
open Models
open JsonHelpers
open Tools

// ---------------------------------------------------------------------------
// System prompts
// ---------------------------------------------------------------------------

let private analystSystemPrompt =
    "You are the Integrisight.ai integration analyst. You help users understand \
their Azure Integration Services landscape by querying the dependency graph.\n\n\
Rules:\n\
1. ALWAYS use the provided tools to retrieve data. Never fabricate component \
names, IDs, counts, or relationships.\n\
2. If the user asks about something not in the graph data, say so explicitly.\n\
3. When citing components, include their display names and types.\n\
4. For impact analysis, explain what each impacted component does and why \
it would be affected.\n\
5. Be concise but thorough. Use bullet points for lists.\n\
6. If a tool returns an error, report it honestly to the user."

let private evaluatorSystemPrompt =
    "You are a quality evaluator for Integrisight.ai analysis responses.\n\n\
You review the integration analyst's response and verify it against the tool call \
evidence provided.\n\n\
You receive:\n\
1. The user's original question.\n\
2. The analyst's response.\n\
3. The complete list of tool calls and their outputs.\n\n\
Rules:\n\
- Check that every component name, ID, count, and relationship cited in the \
response appears in the tool call outputs.\n\
- Check that the response actually answers the user's question.\n\
- If the response fabricates data not present in tool outputs, mark it as FAILED \
with specific citations.\n\
- If the response is accurate but incomplete, mark it as PASSED with a note.\n\
- If the response is accurate and complete, mark it as PASSED.\n\n\
Return ONLY a JSON object with no markdown formatting:\n\
{\n\
  \"verdict\": \"PASSED\" or \"FAILED\",\n\
  \"confidence\": 0.0 to 1.0,\n\
  \"issues\": [\"list of specific issues, empty if PASSED\"],\n\
  \"summary\": \"one-sentence evaluation summary\"\n\
}"


// ---------------------------------------------------------------------------
// Evaluator prompt builder
// ---------------------------------------------------------------------------

let private buildEvaluatorPrompt
    (userPrompt: string)
    (analystResponse: string)
    (toolCalls: ToolCallRecord list)
    : string
    =
    let toolCallText =
        if toolCalls.IsEmpty then
            "(no tool calls were made)"
        else
            toolCalls
            |> List.mapi (fun i tc ->
                let args = tc.Arguments.GetRawText()
                let output = tc.Output |> Option.defaultValue ""
                $"--- Tool Call {i + 1} ---\nTool: {tc.ToolName}\nArguments: {args}\nOutput: {output}")
            |> String.concat "\n"

    $"## User Question\n{userPrompt}\n\n## Analyst Response\n{analystResponse}\n\n## Tool Call History\n{toolCallText}\n\nPlease evaluate the analyst's response and return your verdict as JSON."


// ---------------------------------------------------------------------------
// Run loop — handles polling and tool call dispatch
// ---------------------------------------------------------------------------

/// Collect all messages from an AsyncCollectionResult into a list.
let private collectMessages (result: AsyncCollectionResult<ThreadMessage>) =
    task {
        let mutable msgs: ThreadMessage list = []
        let enumerator = result.GetAsyncEnumerator()
        let mutable keepGoing = true
        while keepGoing do
            let! hasNext = enumerator.MoveNextAsync()
            if hasNext then
                msgs <- enumerator.Current :: msgs
            else
                keepGoing <- false
        return List.rev msgs
    }

/// Get text from the last assistant message in a thread.
let private getLastAssistantText (assistantClient: AssistantClient) (threadId: string) =
    task {
        let messagesResult = assistantClient.GetMessagesAsync(threadId, null)
        let! allMessages = collectMessages messagesResult
        return
            allMessages
            |> List.tryFind (fun m -> m.Role = MessageRole.Assistant)
            |> Option.map (fun m ->
                m.Content
                |> Seq.tryFind (fun c -> c.Text <> null)
                |> Option.map (fun c -> c.Text)
                |> Option.defaultValue "")
            |> Option.defaultValue ""
    }

/// Execute a single assistant run on a new thread, dispatching tool calls.
/// Returns (assistantText, toolCallRecords).
let private runWithTools
    (assistantClient: AssistantClient)
    (assistantId: string)
    (userPrompt: string)
    (toolMap: Map<string, string -> Task<string>>)
    (logger: ILogger)
    : Task<string * ToolCallRecord list>
    =
    task {
        // Create thread
        let! threadResult = assistantClient.CreateThreadAsync(ThreadCreationOptions())
        let thread = threadResult.Value
        let mutable threadCreated = true

        let cleanup () =
            task {
                if threadCreated then
                    try
                        let! _ = assistantClient.DeleteThreadAsync(thread.Id)
                        ()
                    with ex ->
                        logger.LogWarning(ex, "thread_delete_failed thread_id={ThreadId}", thread.Id)
            }

        try
            // Add user message
            let content = [| MessageContent.FromText(userPrompt) |] :> IEnumerable<MessageContent>
            let! _ = assistantClient.CreateMessageAsync(thread.Id, MessageRole.User, content)

            // Start run
            let! runResult = assistantClient.CreateRunAsync(thread.Id, assistantId, RunCreationOptions())
            let mutable run = runResult.Value
            let mutable keepPolling = true
            let mutable collectedToolCalls: ToolCallRecord list = []

            while keepPolling do
                let status = run.Status

                if status = RunStatus.Completed
                   || status = RunStatus.Failed
                   || status = RunStatus.Cancelled
                   || status = RunStatus.Expired then
                    keepPolling <- false

                elif status = RunStatus.RequiresAction then
                    // Dispatch tool calls and submit outputs
                    let toolOutputs = List<ToolOutput>()

                    for action in run.RequiredActions do
                        let toolName = action.FunctionName
                        let argsJson = action.FunctionArguments

                        let! output =
                            match Map.tryFind toolName toolMap with
                            | Some f ->
                                task {
                                    try
                                        return! f argsJson
                                    with ex ->
                                        logger.LogWarning(ex, "tool_execution_failed tool={Tool}", toolName)
                                        return JsonSerializer.Serialize({| error = ex.Message |})
                                }
                            | None ->
                                Task.FromResult(
                                    JsonSerializer.Serialize({| error = $"Unknown tool: {toolName}" |})
                                )

                        toolOutputs.Add(ToolOutput(action.ToolCallId, output))

                        collectedToolCalls <-
                            collectedToolCalls
                            @ [ { ToolName = toolName
                                  Arguments =
                                      try
                                          JsonDocument.Parse(argsJson).RootElement
                                      with _ ->
                                          JsonDocument.Parse("{}").RootElement
                                  Output = Some output } ]

                    let! r = assistantClient.SubmitToolOutputsToRunAsync(thread.Id, run.Id, toolOutputs)
                    run <- r.Value

                else
                    // Queued or InProgress — wait then poll
                    do! Task.Delay(TimeSpan.FromMilliseconds(500.0))
                    let! r = assistantClient.GetRunAsync(thread.Id, run.Id)
                    run <- r.Value

            // Extract the last assistant message
            let! assistantText = getLastAssistantText assistantClient thread.Id
            do! cleanup ()
            threadCreated <- false
            return assistantText, collectedToolCalls

        with ex ->
            do! cleanup ()
            threadCreated <- false
            raise ex
            return "", []
    }

/// Run the evaluator agent (no tools) and parse its JSON verdict.
let private runEvaluator
    (assistantClient: AssistantClient)
    (evaluatorAssistantId: string)
    (userPrompt: string)
    (analystResponse: string)
    (toolCalls: ToolCallRecord list)
    (logger: ILogger)
    : Task<EvaluationResult>
    =
    task {
        let evalPrompt = buildEvaluatorPrompt userPrompt analystResponse toolCalls

        let! threadResult = assistantClient.CreateThreadAsync(ThreadCreationOptions())
        let thread = threadResult.Value

        let cleanup () =
            task {
                try
                    let! _ = assistantClient.DeleteThreadAsync(thread.Id)
                    ()
                with ex ->
                    logger.LogWarning(ex, "eval_thread_delete_failed thread_id={ThreadId}", thread.Id)
            }

        try
            let content = [| MessageContent.FromText(evalPrompt) |] :> IEnumerable<MessageContent>
            let! _ = assistantClient.CreateMessageAsync(thread.Id, MessageRole.User, content)
            let! runResult = assistantClient.CreateRunAsync(thread.Id, evaluatorAssistantId, RunCreationOptions())
            let mutable run = runResult.Value

            while run.Status = RunStatus.Queued || run.Status = RunStatus.InProgress do
                do! Task.Delay(TimeSpan.FromMilliseconds(500.0))
                let! r = assistantClient.GetRunAsync(thread.Id, run.Id)
                run <- r.Value

            let! evalText = getLastAssistantText assistantClient thread.Id
            do! cleanup ()

            // Parse JSON verdict
            try
                let cleaned =
                    let s = evalText.Trim()
                    if s.StartsWith("```") then
                        s.Split('\n')
                        |> Array.filter (fun l -> not (l.TrimStart().StartsWith("```")))
                        |> String.concat "\n"
                    else
                        s

                let doc = JsonDocument.Parse(cleaned)
                let root = doc.RootElement

                let verdict =
                    match tryGetProp "verdict" root with
                    | true, v ->
                        EvaluationVerdict.ofString (v.GetString() |> Option.ofObj |> Option.defaultValue "PASSED")
                    | _ -> Passed

                let confidence =
                    match tryGetProp "confidence" root with
                    | true, v -> v.GetDouble()
                    | _ -> 0.5

                let issues =
                    match tryGetProp "issues" root with
                    | true, v when v.ValueKind = JsonValueKind.Array ->
                        [ for i in v.EnumerateArray() ->
                              i.GetString() |> Option.ofObj |> Option.defaultValue "" ]
                    | _ -> []

                let summary =
                    match tryGetProp "summary" root with
                    | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                    | _ -> ""

                return { Verdict = verdict; Confidence = confidence; Issues = issues; Summary = summary }

            with ex ->
                logger.LogWarning(ex, "evaluator_parse_failed raw={Raw}", evalText)
                return
                    {
                        Verdict = Passed
                        Confidence = 0.3
                        Issues = []
                        Summary = "Evaluator response could not be parsed; defaulting to PASSED."
                    }

        with ex ->
            do! cleanup ()
            logger.LogWarning(ex, "evaluator_run_failed")
            return
                {
                    Verdict = Passed
                    Confidence = 0.0
                    Issues = []
                    Summary = $"Evaluator failed: {ex.Message}"
                }
    }


// ---------------------------------------------------------------------------
// Orchestrator
// ---------------------------------------------------------------------------

type AgentOrchestrator(settings: Config.Settings, toolDefs: AnalysisToolDefinition list, logger: ILogger) =

    let mutable assistantClient: AssistantClient option = None
    let mutable analystAssistantId: string option = None
    let mutable evaluatorAssistantId: string option = None

    let toolMap: Map<string, string -> Task<string>> =
        toolDefs
        |> List.map (fun td -> td.Name, td.Execute)
        |> Map.ofList

    let ensureClient () =
        match assistantClient with
        | Some c -> c
        | None ->
            let credential = Credential.createCredential settings.AzureClientId
            let azureClient = AzureOpenAIClient(Uri(settings.FoundryProjectEndpoint), credential)
            let c = azureClient.GetAssistantClient()
            assistantClient <- Some c
            c

    let ensureAssistants () =
        task {
            let client = ensureClient ()

            if analystAssistantId.IsNone then
                // Build analyst tool definitions (OpenAI.Assistants.FunctionToolDefinition)
                let azureToolDefs =
                    toolDefs
                    |> List.map (fun td ->
                        let funcDef = FunctionToolDefinition(FunctionName = td.Name)
                        funcDef.Description <- td.Description
                        funcDef.Parameters <- BinaryData.FromString(td.ParametersSchema)
                        funcDef :> OpenAI.Assistants.ToolDefinition)

                let analystOptions = AssistantCreationOptions()
                analystOptions.Name <- "integration-analyst"
                analystOptions.Instructions <- analystSystemPrompt
                for t in azureToolDefs do
                    analystOptions.Tools.Add(t)

                let! analystResult = client.CreateAssistantAsync(settings.FoundryModelDeploymentName, analystOptions)
                analystAssistantId <- Some analystResult.Value.Id
                logger.LogInformation("analyst_assistant_created assistant_id={AssistantId}", analystResult.Value.Id)

                let evaluatorOptions = AssistantCreationOptions()
                evaluatorOptions.Name <- "quality-evaluator"
                evaluatorOptions.Instructions <- evaluatorSystemPrompt

                let! evalResult = client.CreateAssistantAsync(settings.FoundryModelDeploymentName, evaluatorOptions)
                evaluatorAssistantId <- Some evalResult.Value.Id
                logger.LogInformation("evaluator_assistant_created assistant_id={AssistantId}", evalResult.Value.Id)
        }

    /// Run the full analyst → evaluator flow with up to 1 retry on FAILED.
    member _.RunAnalysisAsync(userPrompt: string) =
        task {
            do! ensureAssistants ()

            let client = ensureClient ()
            let analystId = analystAssistantId.Value
            let evaluatorId = evaluatorAssistantId.Value

            let mutable retryCount = 0

            // Step 1: Run analyst
            let! (analystResponse, toolCallRecords) =
                runWithTools client analystId userPrompt toolMap logger

            // Step 2: Evaluate
            let! evalResult =
                runEvaluator client evaluatorId userPrompt analystResponse toolCallRecords logger

            // Step 3: Retry once on FAILED
            let! finalResponse, finalToolCalls, finalEval =
                task {
                    if evalResult.Verdict = EvalFailed && retryCount < 1 then
                        retryCount <- retryCount + 1
                        let issuesText =
                            if evalResult.Issues.IsEmpty then
                                evalResult.Summary
                            else
                                String.concat "; " evalResult.Issues
                        let revisionPrompt =
                            $"Your previous response had issues: {issuesText}. \
                              Please revise your answer using the tools to verify your claims."

                        let! (r2, tc2) = runWithTools client analystId revisionPrompt toolMap logger
                        let! eval2 = runEvaluator client evaluatorId userPrompt r2 tc2 logger
                        return r2, tc2, eval2
                    else
                        return analystResponse, toolCallRecords, evalResult
                }

            return
                {
                    Response = finalResponse
                    ToolCalls = finalToolCalls
                    Evaluation = Some finalEval
                    RetryCount = retryCount
                }
        }

    /// Clean up assistants from Azure AI Foundry.
    member _.CloseAsync() =
        task {
            let client = ensureClient ()

            let deleteAssistant (assistantIdOpt: string option) =
                task {
                    match assistantIdOpt with
                    | None -> ()
                    | Some id ->
                        try
                            let! _ = client.DeleteAssistantAsync(id)
                            ()
                        with ex ->
                            logger.LogWarning(ex, "assistant_delete_failed assistant_id={AssistantId}", id)
                }

            do! deleteAssistant analystAssistantId
            do! deleteAssistant evaluatorAssistantId
            analystAssistantId <- None
            evaluatorAssistantId <- None
            assistantClient <- None
        }
