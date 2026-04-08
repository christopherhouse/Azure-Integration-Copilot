/// Agent orchestrator — analyst + evaluator using Microsoft Semantic Kernel
/// with the Azure AI Foundry Agents Service backend (AzureAIAgent).
///
/// Mirrors Python workers/analysis/agent.py which uses the
/// ``agent-framework-core`` + ``agent-framework-foundry`` packages.
///
/// Pattern:
///   AzureAIAgent + AzureAIAgentThread — Semantic Kernel's high-level
///   agent abstraction that handles run polling, tool-call dispatch, and
///   thread management automatically.  Analyst tools are registered as
///   KernelPlugin functions; SK dispatches them and feeds results back.
///
/// On FAILED evaluation verdict, the analyst is re-prompted once (max 1 retry).
module IntegrisightWorkerAnalysis.AgentOrchestrator

open System
open System.Collections.Generic
open System.Text.Json
open System.Threading
open System.Threading.Tasks
open Azure.AI.Agents.Persistent
open Microsoft.Extensions.Logging
open Microsoft.SemanticKernel
open Microsoft.SemanticKernel.ChatCompletion
open Microsoft.SemanticKernel.Agents
open Microsoft.SemanticKernel.Agents.AzureAI
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
// SK KernelPlugin builder — wraps the four F# tool functions
// ---------------------------------------------------------------------------

/// Build a KernelPlugin that wraps the four analysis tools as KernelFunctions.
/// SK uses these to auto-dispatch tool calls during an agent run.
let private buildAnalystPlugin (toolDefs: AnalysisToolDefinition list) : KernelPlugin =
    let functions =
        toolDefs
        |> List.map (fun td ->
            // Wrap the tool as a KernelFunction with a string input / string output
            let func =
                KernelFunctionFactory.CreateFromMethod(
                    Func<string, Task<string>>(fun (args: string) -> td.Execute(args)),
                    td.Name,
                    td.Description
                )
            func)

    KernelPluginFactory.CreateFromFunctions("analysis_tools", functions)


// ---------------------------------------------------------------------------
// Parse evaluator response
// ---------------------------------------------------------------------------

let private parseEvaluation (evalText: string) (logger: ILogger) : EvaluationResult =
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

        { Verdict = verdict; Confidence = confidence; Issues = issues; Summary = summary }

    with ex ->
        logger.LogWarning(ex, "evaluator_parse_failed raw={Raw}", evalText)
        {
            Verdict = Passed
            Confidence = 0.3
            Issues = []
            Summary = "Evaluator response could not be parsed; defaulting to PASSED."
        }


// ---------------------------------------------------------------------------
// Run analyst with SK AzureAIAgent
// ---------------------------------------------------------------------------

/// Collect all messages from an IAsyncEnumerable.
let private collectAsync<'T> (seq: IAsyncEnumerable<'T>) (ct: CancellationToken) =
    task {
        let mutable items: 'T list = []
        let enumerator = seq.GetAsyncEnumerator(ct)
        let mutable keepGoing = true
        while keepGoing do
            let! hasNext = enumerator.MoveNextAsync()
            if hasNext then
                items <- enumerator.Current :: items
            else
                keepGoing <- false
        return List.rev items
    }

/// Run the analyst agent on a single prompt.  Returns the text response and
/// a list of tool calls extracted from the message items.
let private runAgent
    (agent: AzureAIAgent)
    (userPrompt: string)
    (logger: ILogger)
    (ct: CancellationToken)
    : Task<string * ToolCallRecord list>
    =
    task {
        let thread = AzureAIAgentThread(agent.Client)

        let cleanup () =
            task {
                try
                    do! thread.DeleteAsync()
                with ex ->
                    logger.LogWarning(ex, "thread_delete_failed")
            }

        try
            let messages =
                [| ChatMessageContent(AuthorRole.User, userPrompt) |]
                :> ICollection<ChatMessageContent>

            let! responseItems = collectAsync (agent.InvokeAsync(messages, thread, AgentInvokeOptions(), ct)) ct

            let mutable toolCalls: ToolCallRecord list = []
            let mutable responseText = ""

            for item in responseItems do
                let msg = item.Message
                if msg <> null then
                    for contentItem in msg.Items do
                        match contentItem with
                        | :? FunctionCallContent as fc ->
                            let argsJson =
                                if fc.Arguments <> null then
                                    try
                                        JsonSerializer.Serialize(fc.Arguments :> IDictionary<string, obj>)
                                    with _ -> "{}"
                                else "{}"
                            let argsElem =
                                try JsonDocument.Parse(argsJson).RootElement
                                with _ -> JsonDocument.Parse("{}").RootElement
                            toolCalls <-
                                toolCalls
                                @ [ { ToolName = fc.FunctionName |> Option.ofObj |> Option.defaultValue ""
                                      Arguments = argsElem
                                      Output = None } ]
                        | :? FunctionResultContent as fr ->
                            let result : string =
                                match box fr.Result with
                                | null -> ""
                                | r ->
                                    match r.ToString() with
                                    | null -> ""
                                    | s -> s
                            // Attach result to the most recent matching tool call
                            toolCalls <-
                                let frFuncName = fr.FunctionName |> Option.ofObj |> Option.defaultValue ""
                                let rec attachResult lst =
                                    match lst with
                                    | [] -> []
                                    | tc :: rest when tc.Output.IsNone && tc.ToolName = frFuncName ->
                                        { tc with Output = Some result } :: rest
                                    | tc :: rest -> tc :: attachResult rest
                                List.rev (attachResult (List.rev toolCalls))
                        | _ -> ()

                    if msg.Role = AuthorRole.Assistant && not (String.IsNullOrEmpty msg.Content) then
                        responseText <- msg.Content |> Option.ofObj |> Option.defaultValue responseText

            do! cleanup ()
            return responseText, toolCalls

        with ex ->
            do! cleanup ()
            raise ex
            return "", []
    }


/// Run the evaluator agent (no tools) on the eval prompt. Returns raw text.
let private runEvaluatorAgent
    (agent: AzureAIAgent)
    (evalPrompt: string)
    (logger: ILogger)
    (ct: CancellationToken)
    : Task<string>
    =
    task {
        let thread = AzureAIAgentThread(agent.Client)

        let cleanup () =
            task {
                try
                    do! thread.DeleteAsync()
                with ex ->
                    logger.LogWarning(ex, "eval_thread_delete_failed")
            }

        try
            let messages =
                [| ChatMessageContent(AuthorRole.User, evalPrompt) |]
                :> ICollection<ChatMessageContent>

            let! responseItems = collectAsync (agent.InvokeAsync(messages, thread, AgentInvokeOptions(), ct)) ct

            let text =
                responseItems
                |> List.tryFindBack (fun item ->
                    let msg = item.Message
                    not (isNull (box msg))
                    && msg.Role = AuthorRole.Assistant
                    && not (String.IsNullOrEmpty msg.Content))
                |> Option.map (fun item ->
                    item.Message.Content |> Option.ofObj |> Option.defaultValue "")
                |> Option.defaultValue ""

            do! cleanup ()
            return text

        with ex ->
            do! cleanup ()
            logger.LogWarning(ex, "evaluator_run_failed")
            return ""
    }


// ---------------------------------------------------------------------------
// Orchestrator
// ---------------------------------------------------------------------------

type AgentOrchestrator
    (
        settings: Config.Settings,
        toolDefs: AnalysisToolDefinition list,
        logger: ILogger
    ) =

    let mutable agentsClient: PersistentAgentsClient option = None
    let mutable analystAgent: AzureAIAgent option = None
    let mutable evaluatorAgent: AzureAIAgent option = None

    let ensureClient () =
        match agentsClient with
        | Some c -> c
        | None ->
            let credential = Credential.createCredential settings.AzureClientId
            let client = AzureAIAgent.CreateAgentsClient(settings.FoundryProjectEndpoint, credential)
            agentsClient <- Some client
            client

    let ensureAgents () =
        task {
            if analystAgent.IsNone then
                let client = ensureClient ()

                // Build the analyst Kernel with tool plugin
                let analystPlugin = buildAnalystPlugin toolDefs
                let analystKernel =
                    Kernel.CreateBuilder()
                        .Build()
                analystKernel.Plugins.Add(analystPlugin)

                // Create the persistent agent definition via Foundry
                let! analystDef =
                    client.Administration.CreateAgentAsync(
                        settings.FoundryModelDeploymentName,
                        name = "integration-analyst",
                        description = null,
                        instructions = analystSystemPrompt
                    )

                let analyst = AzureAIAgent(analystDef.Value, client, [ analystPlugin ])
                analystAgent <- Some analyst
                logger.LogInformation("analyst_agent_created agent_id={AgentId}", analystDef.Value.Id)

                // Evaluator has no tools
                let! evalDef =
                    client.Administration.CreateAgentAsync(
                        settings.FoundryModelDeploymentName,
                        name = "quality-evaluator",
                        description = null,
                        instructions = evaluatorSystemPrompt
                    )

                let evaluator = AzureAIAgent(evalDef.Value, client)
                evaluatorAgent <- Some evaluator
                logger.LogInformation("evaluator_agent_created agent_id={AgentId}", evalDef.Value.Id)
        }

    /// Run the full analyst → evaluator flow with up to 1 retry on FAILED.
    member _.RunAnalysisAsync(userPrompt: string, ?ct: CancellationToken) =
        task {
            let ct = defaultArg ct CancellationToken.None
            do! ensureAgents ()

            let analyst = analystAgent.Value
            let evaluator = evaluatorAgent.Value

            let mutable retryCount = 0

            // Step 1: Run analyst
            let! (analystResponse, toolCallRecords) = runAgent analyst userPrompt logger ct

            // Step 2: Evaluate
            let evalPrompt = buildEvaluatorPrompt userPrompt analystResponse toolCallRecords
            let! evalText = runEvaluatorAgent evaluator evalPrompt logger ct
            let mutable evalResult = parseEvaluation evalText logger

            // Step 3: Retry once on FAILED
            if evalResult.Verdict = EvalFailed && retryCount < 1 then
                retryCount <- retryCount + 1
                let issuesText =
                    if evalResult.Issues.IsEmpty then evalResult.Summary
                    else String.concat "; " evalResult.Issues
                let revisionPrompt =
                    $"Your previous response had issues: {issuesText}. \
                      Please revise your answer using the tools to verify your claims."

                let! (r2, tc2) = runAgent analyst revisionPrompt logger ct
                let evalPrompt2 = buildEvaluatorPrompt userPrompt r2 tc2
                let! evalText2 = runEvaluatorAgent evaluator evalPrompt2 logger ct
                evalResult <- parseEvaluation evalText2 logger

                return { Response = r2; ToolCalls = tc2; Evaluation = Some evalResult; RetryCount = retryCount }
            else
                return
                    {
                        Response = analystResponse
                        ToolCalls = toolCallRecords
                        Evaluation = Some evalResult
                        RetryCount = retryCount
                    }
        }

    /// Clean up agents from Azure AI Foundry.
    member _.CloseAsync() =
        task {
            let client = ensureClient ()

            let deleteAgent (agentOpt: AzureAIAgent option) =
                task {
                    match agentOpt with
                    | None -> ()
                    | Some a ->
                        try
                            let! _ = client.Administration.DeleteAgentAsync(a.Definition.Id)
                            ()
                        with ex ->
                            logger.LogWarning(ex, "agent_delete_failed agent_id={AgentId}", a.Definition.Id)
                }

            do! deleteAgent analystAgent
            do! deleteAgent evaluatorAgent
            analystAgent <- None
            evaluatorAgent <- None
            agentsClient <- None
        }
