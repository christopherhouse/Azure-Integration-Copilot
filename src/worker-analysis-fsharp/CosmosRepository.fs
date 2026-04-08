/// Cosmos DB repository for analysis documents and graph documents.
///
/// Covers the operations needed by the analysis handler and agent tools,
/// mirroring domains/analysis/repository.py and domains/graph/repository.py.
module IntegrisightWorkerAnalysis.CosmosRepository

open System.Text.Json
open Microsoft.Azure.Cosmos
open Models
open JsonHelpers

[<Literal>]
let private DatabaseName = "integration-copilot"

[<Literal>]
let private AnalysisContainerName = "analyses"

[<Literal>]
let private GraphContainerName = "graph"

// ---------------------------------------------------------------------------
// Client management
// ---------------------------------------------------------------------------

/// Lazy CosmosClient initialised from the endpoint + DefaultAzureCredential.
type CosmosClientProvider(endpoint: string, credential: Azure.Core.TokenCredential) =
    let client = lazy (new CosmosClient(endpoint, credential))
    member _.Client = client.Value


// ---------------------------------------------------------------------------
// Analysis repository
// ---------------------------------------------------------------------------

type AnalysisRepository(provider: CosmosClientProvider) =

    let container () =
        provider.Client
            .GetDatabase(DatabaseName)
            .GetContainer(AnalysisContainerName)

    /// Load an analysis document by (partitionKey, analysisId).
    member _.GetByIdAsync(partitionKey: string, analysisId: string) =
        task {
            try
                let! response =
                    container().ReadItemStreamAsync(
                        analysisId,
                        PartitionKey(partitionKey)
                    )
                if response.IsSuccessStatusCode then
                    use reader = new System.IO.StreamReader(response.Content)
                    let! json = reader.ReadToEndAsync()
                    return Some(analysisOfJson json)
                else
                    return None
            with _ ->
                return None
        }

    /// Upsert an analysis document (full replace).
    member _.UpsertAsync(analysis: Analysis) =
        task {
            let dict = analysisToDict analysis
            let json = JsonSerializer.Serialize(dict)
            use content = new System.IO.MemoryStream(System.Text.Encoding.UTF8.GetBytes(json))
            let! _ =
                container().UpsertItemStreamAsync(
                    content,
                    PartitionKey(analysis.PartitionKey)
                )
            return ()
        }


// ---------------------------------------------------------------------------
// Graph repository (used by agent tools)
// ---------------------------------------------------------------------------

type GraphRepository(provider: CosmosClientProvider) =

    let container () =
        provider.Client
            .GetDatabase(DatabaseName)
            .GetContainer(GraphContainerName)

    /// Get a single component by ID.
    member _.GetComponentAsync(partitionKey: string, componentId: string) =
        task {
            try
                let! response =
                    container().ReadItemStreamAsync(
                        componentId,
                        PartitionKey(partitionKey)
                    )
                if response.IsSuccessStatusCode then
                    use reader = new System.IO.StreamReader(response.Content)
                    let! json = reader.ReadToEndAsync()
                    let doc = JsonDocument.Parse(json)
                    let root = doc.RootElement
                    match tryGetProp "type" root with
                    | true, t when t.GetString() = "component" ->
                        return Some(componentOfElement root)
                    | _ -> return None
                else
                    return None
            with _ ->
                return None
        }

    /// Get the graph summary for a project.
    member _.GetSummaryAsync(partitionKey: string) =
        task {
            let query =
                QueryDefinition(
                    "SELECT * FROM c WHERE c.partitionKey = @pk AND c.type = 'graph_summary'"
                )
                    .WithParameter("@pk", partitionKey)

            let opts = QueryRequestOptions(PartitionKey = PartitionKey(partitionKey))
            use iter = container().GetItemQueryStreamIterator(query, requestOptions = opts)

            let mutable found: GraphSummary option = None

            while iter.HasMoreResults && found.IsNone do
                let! page = iter.ReadNextAsync()
                if page.IsSuccessStatusCode then
                    use reader = new System.IO.StreamReader(page.Content)
                    let! json = reader.ReadToEndAsync()
                    let doc = JsonDocument.Parse(json)
                    match tryGetProp "Documents" doc.RootElement with
                    | true, docs when docs.ValueKind = JsonValueKind.Array ->
                        match docs.EnumerateArray() |> Seq.tryHead with
                        | Some item -> found <- Some(graphSummaryOfElement item)
                        | None -> ()
                    | _ -> ()

            return found
        }

    /// Get neighboring components connected to the given component.
    /// direction: "both" | "incoming" | "outgoing"
    member this.GetNeighborsAsync
        (partitionKey: string, componentId: string, direction: string)
        =
        task {
            let mutable results : (string * Edge * Component) list = []

            // Outgoing edges (component is source)
            if direction = "both" || direction = "outgoing" then
                let query =
                    QueryDefinition(
                        "SELECT * FROM c WHERE c.partitionKey = @pk AND c.type = 'edge' AND c.sourceComponentId = @cid"
                    )
                        .WithParameter("@pk", partitionKey)
                        .WithParameter("@cid", componentId)

                let opts = QueryRequestOptions(PartitionKey = PartitionKey(partitionKey))
                use iter = container().GetItemQueryStreamIterator(query, requestOptions = opts)

                while iter.HasMoreResults do
                    let! page = iter.ReadNextAsync()
                    if page.IsSuccessStatusCode then
                        use reader = new System.IO.StreamReader(page.Content)
                        let! json = reader.ReadToEndAsync()
                        let doc = JsonDocument.Parse(json)
                        match tryGetProp "Documents" doc.RootElement with
                        | true, docs when docs.ValueKind = JsonValueKind.Array ->
                            for item in docs.EnumerateArray() do
                                let edge = edgeOfElement item
                                let! compOpt = this.GetComponentAsync(partitionKey, edge.TargetComponentId)
                                match compOpt with
                                | Some comp -> results <- ("outgoing", edge, comp) :: results
                                | None -> ()
                        | _ -> ()

            // Incoming edges (component is target)
            if direction = "both" || direction = "incoming" then
                let query =
                    QueryDefinition(
                        "SELECT * FROM c WHERE c.partitionKey = @pk AND c.type = 'edge' AND c.targetComponentId = @cid"
                    )
                        .WithParameter("@pk", partitionKey)
                        .WithParameter("@cid", componentId)

                let opts = QueryRequestOptions(PartitionKey = PartitionKey(partitionKey))
                use iter = container().GetItemQueryStreamIterator(query, requestOptions = opts)

                while iter.HasMoreResults do
                    let! page = iter.ReadNextAsync()
                    if page.IsSuccessStatusCode then
                        use reader = new System.IO.StreamReader(page.Content)
                        let! json = reader.ReadToEndAsync()
                        let doc = JsonDocument.Parse(json)
                        match tryGetProp "Documents" doc.RootElement with
                        | true, docs when docs.ValueKind = JsonValueKind.Array ->
                            for item in docs.EnumerateArray() do
                                let edge = edgeOfElement item
                                let! compOpt = this.GetComponentAsync(partitionKey, edge.SourceComponentId)
                                match compOpt with
                                | Some comp -> results <- ("incoming", edge, comp) :: results
                                | None -> ()
                        | _ -> ()

            return List.rev results
        }
