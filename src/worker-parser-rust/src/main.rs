//! Integrisight.ai — Rust parser worker.
//!
//! Runs as a standalone async process.  Pulls `ArtifactScanPassed` events from
//! the `artifact-parser` subscription and parses artifacts into structured
//! components, storing results in Cosmos DB.

use std::sync::atomic::Ordering;

use tracing_subscriber::EnvFilter;

use integrisight_worker_parser_rust::azure::blob::BlobService;
use integrisight_worker_parser_rust::azure::cosmos::CosmosService;
use integrisight_worker_parser_rust::azure::credential::ManagedIdentityCredential;
use integrisight_worker_parser_rust::azure::event_grid::consumer::EventGridConsumer;
use integrisight_worker_parser_rust::azure::event_grid::publisher::EventGridPublisher;
use integrisight_worker_parser_rust::config::Settings;
use integrisight_worker_parser_rust::worker::handler::ParserHandler;
use integrisight_worker_parser_rust::worker::BaseWorker;

const SUBSCRIPTION_NAME: &str = "artifact-parser";

#[tokio::main]
async fn main() {
    // Structured JSON logging, controlled by RUST_LOG env var.
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .json()
        .init();

    let settings = Settings::from_env();

    let credential = ManagedIdentityCredential::new(
        if settings.azure_client_id.is_empty() {
            None
        } else {
            Some(settings.azure_client_id.clone())
        },
    );

    let consumer = EventGridConsumer::new(
        settings.event_grid_namespace_endpoint.clone(),
        settings.event_grid_topic.clone(),
        SUBSCRIPTION_NAME.to_owned(),
        credential.clone(),
    );

    let blob = BlobService::new(
        settings.blob_storage_endpoint.clone(),
        credential.clone(),
    );
    let cosmos = CosmosService::new(
        settings.cosmos_db_endpoint.clone(),
        credential.clone(),
    );
    let publisher = EventGridPublisher::new(
        settings.event_grid_namespace_endpoint.clone(),
        settings.event_grid_topic.clone(),
        credential,
    );

    let handler = ParserHandler::new(blob, cosmos, publisher);
    let worker = BaseWorker::new(consumer, Box::new(handler), 5.0);

    // Graceful shutdown on SIGTERM / SIGINT
    let stop = worker.stop_handle();
    tokio::spawn(async move {
        let mut sigterm =
            tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
                .expect("failed to register SIGTERM handler");
        tokio::select! {
            _ = tokio::signal::ctrl_c() => {
                tracing::info!("received SIGINT, shutting down");
            }
            _ = sigterm.recv() => {
                tracing::info!("received SIGTERM, shutting down");
            }
        }
        stop.store(false, Ordering::Relaxed);
    });

    tracing::info!(
        subscription = SUBSCRIPTION_NAME,
        environment = %settings.environment,
        "parser_worker_starting"
    );
    worker.run().await;
}
