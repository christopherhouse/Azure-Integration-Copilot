/// Web PubSub notification service — mirrors Python shared/pubsub.py.
module IntegrisightWorkerAnalysis.WebPubSubService

open System
open System.Text.Json
open Azure.Messaging.WebPubSub
open Microsoft.Extensions.Logging

[<Literal>]
let private NotificationHub = "notifications"

type PubSubService(endpoint: string, credential: Azure.Core.TokenCredential, logger: ILogger) =

    let client =
        lazy (
            if String.IsNullOrEmpty endpoint then
                null
            else
                WebPubSubServiceClient(Uri(endpoint), NotificationHub, credential)
        )

    /// Send a JSON message to a Web PubSub group.
    member _.SendToGroupAsync(group: string, data: obj) =
        task {
            if String.IsNullOrEmpty endpoint then
                logger.LogWarning("pubsub_not_configured")
                return ()
            else
                try
                    let json = JsonSerializer.Serialize(data)
                    let content = BinaryData.FromString(json)
                    let! _ = client.Value.SendToGroupAsync(group, content, "application/json")
                    return ()
                with ex ->
                    logger.LogWarning(ex, "pubsub_send_failed group={Group}", group)
        }
