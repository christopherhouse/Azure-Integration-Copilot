/// Event Grid Namespace pull-delivery consumer and publisher.
///
/// Mirrors Python shared/event_consumer.py and shared/events.py.
/// Uses Azure.Messaging.EventGrid.Namespaces for pull delivery (CloudEvents format).
module IntegrisightWorkerAnalysis.EventGridClient

open System
open System.Collections.Generic
open System.Text.Json
open Azure.Messaging
open Azure.Messaging.EventGrid.Namespaces
open Microsoft.Extensions.Logging

// ---------------------------------------------------------------------------
// Received event envelope
// ---------------------------------------------------------------------------

/// Wrapper around a received CloudEvent and its lock token.
type ReceivedEventDetail =
    {
        EventId: string
        EventType: string
        Data: JsonElement
        LockToken: string
        TraceParent: string option
        TraceState: string option
    }

// ---------------------------------------------------------------------------
// Consumer
// ---------------------------------------------------------------------------

type EventGridConsumer
    (
        endpoint: string,
        topicName: string,
        subscriptionName: string,
        credential: Azure.Core.TokenCredential,
        logger: ILogger
    ) =

    let client =
        lazy (EventGridReceiverClient(Uri(endpoint), topicName, subscriptionName, credential))

    /// Pull a batch of events. Returns parsed detail records.
    member _.ReceiveAsync(?maxEvents: int, ?maxWaitTimeSecs: int) =
        task {
            let maxEvts = maxEvents |> Option.map (fun n -> Nullable<int>(n)) |> Option.defaultValue (Nullable<int>())
            let waitTime =
                maxWaitTimeSecs
                |> Option.map (fun s -> Nullable<TimeSpan>(TimeSpan.FromSeconds(float s)))
                |> Option.defaultValue (Nullable<TimeSpan>())

            let! response = client.Value.ReceiveAsync(maxEvts, waitTime)

            let details = response.Value.Details
            if details = null then
                return []
            else
                // Helper: parse JSON into a standalone JsonElement (document is disposed immediately).
                let parseData (s: string) =
                    use doc = JsonDocument.Parse(s)
                    doc.RootElement.Clone()

                return
                    [ for detail in details do
                          let evt : CloudEvent = detail.Event
                          if evt <> null then
                              let data =
                                  if evt.Data <> null then
                                      try parseData (evt.Data.ToString())
                                      with _ -> parseData "{}"
                                  else
                                      parseData "{}"

                              let traceParent =
                                  if evt.ExtensionAttributes <> null then
                                      match evt.ExtensionAttributes.TryGetValue("traceparent") with
                                      | true, v -> v |> string |> Some
                                      | _ -> None
                                  else
                                      None

                              let traceState =
                                  if evt.ExtensionAttributes <> null then
                                      match evt.ExtensionAttributes.TryGetValue("tracestate") with
                                      | true, v -> v |> string |> Some
                                      | _ -> None
                                  else
                                      None

                              yield
                                  {
                                      EventId =
                                          evt.Id
                                          |> Option.ofObj
                                          |> Option.defaultValue "unknown"
                                      EventType =
                                          evt.Type
                                          |> Option.ofObj
                                          |> Option.defaultValue ""
                                      Data = data
                                      LockToken = detail.BrokerProperties.LockToken
                                      TraceParent = traceParent
                                      TraceState = traceState
                                  } ]
        }

    /// Acknowledge events so they are removed from the subscription.
    member _.AcknowledgeAsync(lockTokens: string list) =
        task {
            if lockTokens.IsEmpty then
                return ()
            else
                let! result = client.Value.AcknowledgeAsync(lockTokens)
                let failed = result.Value.FailedLockTokens |> Seq.length
                if failed > 0 then
                    logger.LogWarning("acknowledge_partial_failure failed_count={Failed}", failed)
        }

    /// Release events back to the subscription for redelivery.
    member _.ReleaseAsync(lockTokens: string list) =
        task {
            if lockTokens.IsEmpty then
                return ()
            else
                let! result = client.Value.ReleaseAsync(lockTokens, Nullable<ReleaseDelay>())
                let failed = result.Value.FailedLockTokens |> Seq.length
                if failed > 0 then
                    logger.LogWarning("release_partial_failure failed_count={Failed}", failed)
        }

// ---------------------------------------------------------------------------
// Publisher
// ---------------------------------------------------------------------------

type EventGridPublisher
    (
        endpoint: string,
        topicName: string,
        credential: Azure.Core.TokenCredential,
        logger: ILogger
    ) =

    let client = lazy (EventGridSenderClient(Uri(endpoint), topicName, credential))

    /// Publish a single CloudEvent to the configured Event Grid topic.
    member _.PublishAsync(eventType: string, source: string, subject: string, data: Dictionary<string, obj>) =
        task {
            if String.IsNullOrEmpty endpoint then
                logger.LogWarning("event_grid_not_configured event_type={EventType}", eventType)
                return ()
            else
                try
                    let id = $"evt_{Guid.NewGuid():N}"
                    let dataJson = JsonSerializer.Serialize(data)
                    let evt =
                        CloudEvent(
                            source,
                            eventType,
                            BinaryData.FromString(dataJson),
                            "application/json"
                        )
                    evt.Id <- id
                    evt.Subject <- subject
                    evt.Time <- DateTimeOffset.UtcNow

                    // Inject W3C Trace Context into CloudEvent extension attributes so
                    // downstream consumers can continue the distributed trace.
                    // Mirrors Python shared/events.py inject(carrier).
                    let currentActivity = System.Diagnostics.Activity.Current
                    if not (isNull currentActivity) && not (String.IsNullOrEmpty currentActivity.Id) then
                        evt.ExtensionAttributes.["traceparent"] <- currentActivity.Id :> obj
                        if not (String.IsNullOrEmpty currentActivity.TraceStateString) then
                            evt.ExtensionAttributes.["tracestate"] <- currentActivity.TraceStateString :> obj

                    let! _ = client.Value.SendAsync(evt)
                    logger.LogInformation("event_published event_type={EventType} subject={Subject}", eventType, subject)
                with ex ->
                    logger.LogWarning(ex, "event_publish_failed event_type={EventType}", eventType)
        }
