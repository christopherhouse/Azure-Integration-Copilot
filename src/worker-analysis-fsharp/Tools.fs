/// Agent tools — the four functions available to the integration analyst.
///
/// Mirrors Python workers/analysis/tools/:
///   get_project_summary, get_graph_neighbors, get_component_details, run_impact_analysis
///
/// All tools read the current AnalysisContext from a thread-local AsyncLocal value
/// so tenant/project isolation does not need to be passed explicitly to the agent.
module IntegrisightWorkerAnalysis.Tools

open System
open System.Collections.Generic
open System.Text.Json
open System.Threading
open CosmosRepository
open Models
open JsonHelpers

// ---------------------------------------------------------------------------
// Analysis context (mirrors Python's contextvars.ContextVar[AnalysisContext])
// ---------------------------------------------------------------------------

type AnalysisContext =
    {
        TenantId: string
        ProjectId: string
    }

/// AsyncLocal carries the scoped tenant/project context down the async call graph.
let private analysisContextLocal = AsyncLocal<AnalysisContext option>()

/// Set the analysis context and return an IDisposable that restores the previous value.
let setContext (ctx: AnalysisContext) : IDisposable =
    let previous = analysisContextLocal.Value
    analysisContextLocal.Value <- Some ctx
    { new IDisposable with
        member _.Dispose() = analysisContextLocal.Value <- previous }

let private getContext () =
    match analysisContextLocal.Value with
    | Some ctx -> ctx
    | None -> failwith "AnalysisContext is not set — tools must be called inside a scoped context."


// ---------------------------------------------------------------------------
// Tool implementations
// ---------------------------------------------------------------------------

/// get_project_summary — mirrors Python get_project_summary.py
let getProjectSummary (graphRepo: GraphRepository) () =
    task {
        let ctx = getContext ()
        let pk = $"{ctx.TenantId}:{ctx.ProjectId}"
        let! summaryOpt = graphRepo.GetSummaryAsync(pk)

        let result =
            match summaryOpt with
            | None ->
                JsonSerializer.Serialize({| error = "No graph data found for this project." |})
            | Some s ->
                let componentCounts =
                    try
                        JsonSerializer.Deserialize<Dictionary<string, int>>(s.ComponentCounts.GetRawText())
                    with _ ->
                        Dictionary<string, int>()
                let edgeCounts =
                    try
                        JsonSerializer.Deserialize<Dictionary<string, int>>(s.EdgeCounts.GetRawText())
                    with _ ->
                        Dictionary<string, int>()
                JsonSerializer.Serialize(
                    {|
                        totalComponents = s.TotalComponents
                        totalEdges = s.TotalEdges
                        componentCounts = componentCounts
                        edgeCounts = edgeCounts
                        graphVersion = s.GraphVersion
                    |}
                )
        return result
    }


/// get_graph_neighbors — mirrors Python get_graph_neighbors.py
let getGraphNeighbors (graphRepo: GraphRepository) (args: string) =
    task {
        let ctx = getContext ()
        let pk = $"{ctx.TenantId}:{ctx.ProjectId}"

        use doc = JsonDocument.Parse(args)
        let root = doc.RootElement

        let componentId =
            match tryGetProp "component_id" root with
            | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
            | _ ->
                match tryGetProp "componentId" root with
                | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                | _ -> ""

        let direction =
            match tryGetProp "direction" root with
            | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue "both"
            | _ -> "both"

        let! neighbors = graphRepo.GetNeighborsAsync(pk, componentId, direction)

        let neighborDtos =
            neighbors
            |> List.map (fun (dir, edge, comp) ->
                {|
                    direction = dir
                    edge =
                        {|
                            id = edge.Id
                            edgeType = edge.EdgeType
                            sourceComponentId = edge.SourceComponentId
                            targetComponentId = edge.TargetComponentId
                        |}
                    ``component`` =
                        {|
                            id = comp.Id
                            name = comp.Name
                            displayName = comp.DisplayName
                            componentType = comp.ComponentType
                        |}
                |})

        return JsonSerializer.Serialize({| neighbors = neighborDtos; count = neighborDtos.Length |})
    }


/// get_component_details — mirrors Python get_component_details.py
let getComponentDetails (graphRepo: GraphRepository) (args: string) =
    task {
        let ctx = getContext ()
        let pk = $"{ctx.TenantId}:{ctx.ProjectId}"

        use doc = JsonDocument.Parse(args)
        let root = doc.RootElement

        let componentId =
            match tryGetProp "component_id" root with
            | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
            | _ ->
                match tryGetProp "componentId" root with
                | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                | _ -> ""

        let! compOpt = graphRepo.GetComponentAsync(pk, componentId)

        let result =
            match compOpt with
            | None ->
                JsonSerializer.Serialize({| error = $"Component '{componentId}' not found." |})
            | Some c ->
                let properties =
                    try
                        JsonSerializer.Deserialize<Dictionary<string, obj>>(c.Properties.GetRawText())
                    with _ ->
                        Dictionary<string, obj>()
                JsonSerializer.Serialize(
                    {|
                        id = c.Id
                        name = c.Name
                        displayName = c.DisplayName
                        componentType = c.ComponentType
                        properties = properties
                        tags = c.Tags
                        artifactId = c.ArtifactId
                        graphVersion = c.GraphVersion
                    |}
                )
        return result
    }


/// run_impact_analysis — mirrors Python run_impact_analysis.py
/// Performs a BFS traversal from the given component.
let runImpactAnalysis (graphRepo: GraphRepository) (args: string) =
    task {
        let ctx = getContext ()
        let pk = $"{ctx.TenantId}:{ctx.ProjectId}"

        use doc = JsonDocument.Parse(args)
        let root = doc.RootElement

        let componentId =
            match tryGetProp "component_id" root with
            | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
            | _ ->
                match tryGetProp "componentId" root with
                | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue ""
                | _ -> ""

        let direction =
            match tryGetProp "direction" root with
            | true, v -> v.GetString() |> Option.ofObj |> Option.defaultValue "downstream"
            | _ -> "downstream"

        let maxDepth =
            match tryGetProp "max_depth" root with
            | true, v -> min (v.GetInt32()) 5
            | _ ->
                match tryGetProp "maxDepth" root with
                | true, v -> min (v.GetInt32()) 5
                | _ -> 3

        // Map direction to edge query direction
        let edgeDirection = if direction = "downstream" then "outgoing" else "incoming"

        // BFS traversal
        let visited = System.Collections.Generic.HashSet<string>()
        let queue = System.Collections.Generic.Queue<struct (string * int)>()
        queue.Enqueue(struct (componentId, 0))
        visited.Add(componentId) |> ignore

        let mutable impacted : list<{| id: string; name: string; displayName: string; componentType: string; depth: int |}> = []

        while queue.Count > 0 do
            let struct (currentId, depth) = queue.Dequeue()
            if depth < maxDepth then
                let! neighbors = graphRepo.GetNeighborsAsync(pk, currentId, edgeDirection)
                for (_, _, comp) in neighbors do
                    if not (visited.Contains(comp.Id)) then
                        visited.Add(comp.Id) |> ignore
                        // Prepend (O(1)) instead of append; reversed at end.
                        impacted <-
                            {|
                                id = comp.Id
                                name = comp.Name
                                displayName = comp.DisplayName
                                componentType = comp.ComponentType
                                depth = depth + 1
                            |}
                            :: impacted
                        queue.Enqueue(struct (comp.Id, depth + 1))

        // Reverse once (O(n)) to restore BFS order.
        let impacted = List.rev impacted

        // Get root component info
        let! rootOpt = graphRepo.GetComponentAsync(pk, componentId)
        let rootInfo =
            match rootOpt with
            | Some r ->
                {| id = componentId; name = r.Name; componentType = r.ComponentType |}
            | None ->
                {| id = componentId; name = componentId; componentType = "unknown" |}

        return
            JsonSerializer.Serialize(
                {|
                    rootComponent = rootInfo
                    direction = direction
                    maxDepth = maxDepth
                    impactedComponents = impacted
                    totalImpacted = impacted.Length
                |}
            )
    }


// ---------------------------------------------------------------------------
// Tool registry
// ---------------------------------------------------------------------------

/// A named tool: name, description, JSON parameter schema, and async executor.
type AnalysisToolDefinition =
    {
        Name: string
        Description: string
        /// JSON Schema for the tool parameters (passed to the agent framework).
        ParametersSchema: string
        /// Execute the tool given JSON-encoded arguments; returns JSON string.
        Execute: string -> System.Threading.Tasks.Task<string>
    }

let buildToolDefinitions (graphRepo: GraphRepository) : AnalysisToolDefinition list =
    [
        {
            Name = "get_project_summary"
            Description =
                "Get a summary of the integration project's dependency graph. \
                 Returns total component and edge counts broken down by type."
            ParametersSchema = """{"type":"object","properties":{},"required":[]}"""
            Execute = fun _ -> getProjectSummary graphRepo ()
        }
        {
            Name = "get_graph_neighbors"
            Description =
                "Get the neighboring components connected to a given component. \
                 Returns incoming, outgoing, or both directions."
            ParametersSchema =
                """{
  "type": "object",
  "properties": {
    "component_id": {
      "type": "string",
      "description": "The component ID to find neighbors for."
    },
    "direction": {
      "type": "string",
      "description": "Edge direction filter: 'both', 'incoming', or 'outgoing'.",
      "enum": ["both","incoming","outgoing"]
    }
  },
  "required": ["component_id"]
}"""
            Execute = fun args -> getGraphNeighbors graphRepo args
        }
        {
            Name = "get_component_details"
            Description =
                "Get detailed information about a specific component in the dependency graph. \
                 Returns the component's type, properties, and tags."
            ParametersSchema =
                """{
  "type": "object",
  "properties": {
    "component_id": {
      "type": "string",
      "description": "The component ID to look up."
    }
  },
  "required": ["component_id"]
}"""
            Execute = fun args -> getComponentDetails graphRepo args
        }
        {
            Name = "run_impact_analysis"
            Description =
                "Perform a breadth-first traversal from a component to find all transitively \
                 dependent components. Returns the root component, list of impacted components, \
                 and total count."
            ParametersSchema =
                """{
  "type": "object",
  "properties": {
    "component_id": {
      "type": "string",
      "description": "The component ID to start traversal from."
    },
    "direction": {
      "type": "string",
      "description": "Traversal direction: 'downstream' (outgoing) or 'upstream' (incoming).",
      "enum": ["downstream","upstream"]
    },
    "max_depth": {
      "type": "integer",
      "description": "Maximum traversal depth (default 3, capped at 5)."
    }
  },
  "required": ["component_id","direction"]
}"""
            Execute = fun args -> runImpactAnalysis graphRepo args
        }
    ]
