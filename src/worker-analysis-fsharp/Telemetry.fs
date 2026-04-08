/// Shared OpenTelemetry instrumentation — ActivitySource for worker spans.
///
/// Centralised here so both Worker.fs (which comes before Program.fs in compile
/// order) and Program.fs can reference the same source and service name without
/// creating a circular dependency.
module IntegrisightWorkerAnalysis.Telemetry

open System.Diagnostics

/// Service name used for the OpenTelemetry resource and ActivitySource.
[<Literal>]
let ServiceName = "integrisight-worker-analysis"

/// ActivitySource for this worker.  Used to create spans around event
/// receive / process steps, mirroring the Python worker's `tracer.start_as_current_span`.
let workerSource = new ActivitySource(ServiceName)
