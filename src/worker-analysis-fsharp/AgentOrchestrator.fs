/// Agent orchestrator — analyst + evaluator using Microsoft Agent Framework
/// (Microsoft.Agents.AI + Microsoft.Agents.AI.Foundry) backed by Azure AI Foundry
/// Agents Service.
///
/// Mirrors Python workers/analysis/agent.py which uses
///   from agent_framework import Agent
///   from agent_framework.foundry import FoundryChatClient
///
/// The .NET equivalent:
///   Azure.AI.Projects.AIProjectClient + .AsAIAgent() extension from
///   Microsoft.Agents.AI.Foundry → ChatClientAgent
///
/// On a FAILED evaluation verdict, the analyst is re-prompted once (max 1 retry).
module IntegrisightWorkerAnalysis.AgentOrchestrator

open System
open System.Collections.Generic
open System.Text.Json
open System.Threading
open System.Threading.Tasks
open Azure.AI.Projects
open Microsoft.Agents.AI
open Microsoft.Extensions.AI
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
// Custom AIFunction — wraps AnalysisToolDefinition
//
// AIFunction is abstract in Microsoft.Extensions.AI.
// We override InvokeCoreAsync to call the existing Execute function
// and override JsonSchema to supply the hand-written parameter schema
// from AnalysisToolDefinition.ParametersSchema.
//
// AIFunctionArguments inherits IDictionary<string,obj>; we serialise it
// to JSON and pass the JSON string to the existing Execute implementation.
// ---------------------------------------------------------------------------

type private AnalysisAIFunction(toolDef: AnalysisToolDefinition) =
    inherit AIFunction()

    let schemaElem =
        try JsonDocument.Parse(toolDef.ParametersSchema).RootElement
        with _ -> JsonDocument.Parse("{}").RootElement

    override _.Name = toolDef.Name
    override _.Description = toolDef.Description
    override _.JsonSchema = schemaElem

    override _.InvokeCoreAsync(arguments: AIFunctionArguments, cancellationToken: CancellationToken) : ValueTask<obj> =
        let t =
            task {
                let argsJson =
                    try JsonSerializer.Serialize(arguments :> IDictionary<string, obj>)
                    with _ -> "{}"
                let! result = toolDef.Execute argsJson
                return result :> obj
            }
        ValueTask<obj>(t)


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
// Extract tool call records from an AgentResponse
// ---------------------------------------------------------------------------

let private extractToolCalls (response: AgentResponse) : ToolCallRecord list =
    let mutable calls: ToolCallRecord list = []

    for msg in response.Messages do
        for item in msg.Contents do
            match item with
            | :? FunctionCallContent as fc ->
                let argsJson =
                    try JsonSerializer.Serialize(fc.Arguments :> IDictionary<string, obj>)
                    with _ -> "{}"
                let argsElem =
                    try JsonDocument.Parse(argsJson).RootElement
                    with _ -> JsonDocument.Parse("{}").RootElement
                calls <-
                    calls
                    @ [ { ToolName = fc.Name |> Option.ofObj |> Option.defaultValue ""
                          Arguments = argsElem
                          Output = None } ]
            | :? FunctionResultContent as fr ->
                let result =
                    match box fr.Result with
                    | null -> ""
                    | r ->
                        match r.ToString() with
                        | null -> ""
                        | s -> s
                // Attach result to the most recently unmatched call with the same CallId
                let frCallId = fr.CallId |> Option.ofObj |> Option.defaultValue ""
                calls <-
                    let rec attach lst =
                        match lst with
                        | [] -> []
                        | tc :: rest when tc.Output.IsNone ->
                            // Match by CallId when available, else first unmatched
                            let idMatch = frCallId = "" || tc.Arguments.GetRawText().Contains(frCallId)
                            if idMatch then
                                { tc with Output = Some result } :: rest
                            else
                                tc :: attach rest
                        | tc :: rest -> tc :: attach rest
                    attach calls
            | _ -> ()

    calls


// ---------------------------------------------------------------------------
// Run an agent for a single one-shot prompt
// ---------------------------------------------------------------------------

let private runAgent
    (agent: ChatClientAgent)
    (userPrompt: string)
    (logger: ILogger)
    (ct: CancellationToken)
    : Task<AgentResponse>
    =
    task {
        let! session = agent.CreateSessionAsync(ct)
        let! response = agent.RunAsync(userPrompt, session, null, ct)
        return response
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

    let mutable analystAgent: ChatClientAgent option = None
    let mutable evaluatorAgent: ChatClientAgent option = None

    let ensureAgents () =
        if analystAgent.IsNone then
            let credential = Credential.createCredential settings.AzureClientId
            let client = AIProjectClient(Uri(settings.FoundryProjectEndpoint), credential)

            // Build AITool list from AnalysisToolDefinition list
            let tools: IList<AITool> = toolDefs |> List.map (fun td -> AnalysisAIFunction(td) :> AITool) |> ResizeArray :> IList<AITool>

            let analyst =
                client.AsAIAgent(
                    model       = settings.FoundryModelDeploymentName,
                    instructions= analystSystemPrompt,
                    name        = "integration-analyst",
                    description = null,
                    tools       = tools,
                    clientFactory = null,
                    loggerFactory = null,
                    services    = null)

            let evaluator =
                client.AsAIAgent(
                    model       = settings.FoundryModelDeploymentName,
                    instructions= evaluatorSystemPrompt,
                    name        = "quality-evaluator",
                    description = null,
                    tools       = null,
                    clientFactory = null,
                    loggerFactory = null,
                    services    = null)

            analystAgent   <- Some analyst
            evaluatorAgent <- Some evaluator

            logger.LogInformation("maf_agents_created")

    /// Run the full analyst → evaluator flow with up to 1 retry on FAILED.
    member _.RunAnalysisAsync(userPrompt: string, ?ct: CancellationToken) =
        task {
            let ct = defaultArg ct CancellationToken.None
            ensureAgents ()

            let analyst   = analystAgent.Value
            let evaluator = evaluatorAgent.Value

            // Step 1: Run analyst
            let! analystResponse = runAgent analyst userPrompt logger ct
            let analystText = analystResponse.Text |> Option.ofObj |> Option.defaultValue ""
            let toolCalls   = extractToolCalls analystResponse

            logger.LogInformation(
                "analyst_completed response_len={Len} tool_calls={N}",
                analystText.Length, toolCalls.Length)

            // Step 2: Evaluate
            let evalPrompt = buildEvaluatorPrompt userPrompt analystText toolCalls
            let! evalResponse = runAgent evaluator evalPrompt logger ct
            let evalText = evalResponse.Text |> Option.ofObj |> Option.defaultValue ""
            let mutable evalResult = parseEvaluation evalText logger

            logger.LogInformation(
                "evaluator_verdict={Verdict} confidence={Confidence}",
                string evalResult.Verdict, evalResult.Confidence)

            // Step 3: Retry once on FAILED
            if evalResult.Verdict = EvalFailed then
                let issuesText =
                    if evalResult.Issues.IsEmpty then evalResult.Summary
                    else String.concat "; " evalResult.Issues
                let revisionPrompt =
                    $"Your previous response had issues: {issuesText}. \
                      Please revise your answer using the tools to verify your claims."

                let! r2 = runAgent analyst revisionPrompt logger ct
                let analystText2 = r2.Text |> Option.ofObj |> Option.defaultValue ""
                let tc2 = extractToolCalls r2

                let evalPrompt2 = buildEvaluatorPrompt userPrompt analystText2 tc2
                let! evalResponse2 = runAgent evaluator evalPrompt2 logger ct
                let evalText2 = evalResponse2.Text |> Option.ofObj |> Option.defaultValue ""
                evalResult <- parseEvaluation evalText2 logger

                return
                    {
                        Response = analystText2
                        ToolCalls = tc2
                        Evaluation = Some evalResult
                        RetryCount = 1
                    }
            else
                return
                    {
                        Response = analystText
                        ToolCalls = toolCalls
                        Evaluation = Some evalResult
                        RetryCount = 0
                    }
        }

    /// Reset agents (called on shutdown; agents are ephemeral per session, no cloud cleanup needed).
    member _.CloseAsync() =
        task {
            analystAgent   <- None
            evaluatorAgent <- None
        }
