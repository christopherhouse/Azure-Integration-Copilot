/// CloudEvent type constants — mirrors Python shared/event_types.py.
module IntegrisightWorkerAnalysis.EventTypes

[<Literal>]
let AnalysisRequested = "com.integration-copilot.analysis.requested.v1"

[<Literal>]
let AnalysisCompleted = "com.integration-copilot.analysis.completed.v1"

[<Literal>]
let AnalysisFailed = "com.integration-copilot.analysis.failed.v1"
