//! Worker base class with async pull loop, idempotency, and error handling.
//!
//! Mirrors the Python `workers/base.py` — BaseWorker + WorkerHandler trait.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use serde_json::Value;

use crate::azure::event_grid::consumer::{EventGridConsumer, ReceiveDetails};

/// Error hierarchy for worker processing.
#[derive(Debug, thiserror::Error)]
pub enum WorkerError {
    /// Indicates a transient failure; the event should be released for retry.
    #[error("transient error: {0}")]
    Transient(String),
    /// Indicates a permanent failure; the event should be acknowledged after
    /// calling the handler's `handle_failure` callback.
    #[error("permanent error: {0}")]
    Permanent(String),
}

/// Interface that each domain-specific worker handler must implement.
#[async_trait::async_trait]
pub trait WorkerHandler: Send + Sync {
    /// Return `true` if the event has already been handled (idempotency).
    async fn is_already_processed(&self, event_data: &Value) -> Result<bool, WorkerError>;

    /// Process the event.
    async fn handle(&self, event_data: &Value) -> Result<(), WorkerError>;

    /// Called when a permanent error is raised during processing.
    async fn handle_failure(&self, event_data: &Value, error: &str);
}

/// Async pull-loop worker that receives events from Event Grid Namespace.
pub struct BaseWorker {
    consumer: EventGridConsumer,
    handler: Box<dyn WorkerHandler>,
    poll_interval: std::time::Duration,
    running: Arc<AtomicBool>,
}

impl BaseWorker {
    pub fn new(
        consumer: EventGridConsumer,
        handler: Box<dyn WorkerHandler>,
        poll_interval_secs: f64,
    ) -> Self {
        Self {
            consumer,
            handler,
            poll_interval: std::time::Duration::from_secs_f64(poll_interval_secs),
            running: Arc::new(AtomicBool::new(true)),
        }
    }

    /// Get a handle that can be used to signal the worker to stop.
    pub fn stop_handle(&self) -> Arc<AtomicBool> {
        self.running.clone()
    }

    /// Main pull loop — runs until stop is signalled.
    pub async fn run(&self) {
        tracing::info!("worker_started");
        while self.running.load(Ordering::Relaxed) {
            let details = match self.consumer.receive_events(10, 30).await {
                Ok(d) => d,
                Err(e) => {
                    tracing::error!(error = %e, "receive_events_failed");
                    tokio::time::sleep(self.poll_interval).await;
                    continue;
                }
            };

            if details.is_empty() {
                tokio::time::sleep(self.poll_interval).await;
                continue;
            }

            for detail in details {
                self.process_event(detail).await;
            }
        }
        tracing::info!("worker_stopped");
    }

    async fn process_event(&self, detail: ReceiveDetails) {
        let lock_token = detail.broker_properties.lock_token.clone();
        let event_id = &detail.event.id;
        let event_type = &detail.event.event_type;
        let event_data = detail.event.data.clone().unwrap_or(Value::Object(Default::default()));
        let tenant_id = event_data.get("tenantId").and_then(Value::as_str).unwrap_or("unknown");

        let span = tracing::info_span!("process_event",
            event_id = %event_id,
            event_type = %event_type,
            tenant_id = %tenant_id
        );
        let _guard = span.enter();

        // Tenant validation
        if tenant_id == "unknown" || tenant_id.is_empty() {
            tracing::error!("missing_tenant_id");
            let _ = self.consumer.acknowledge(vec![lock_token]).await;
            return;
        }

        // Idempotency check
        match self.handler.is_already_processed(&event_data).await {
            Ok(true) => {
                tracing::info!("event_already_processed");
                let _ = self.consumer.acknowledge(vec![lock_token]).await;
                return;
            }
            Err(e) => {
                tracing::error!(error = %e, "idempotency_check_failed");
                let _ = self.consumer.release(vec![lock_token]).await;
                return;
            }
            Ok(false) => {}
        }

        // Process
        tracing::info!("event_processing_started");
        match self.handler.handle(&event_data).await {
            Ok(()) => {
                let _ = self.consumer.acknowledge(vec![lock_token]).await;
                tracing::info!("event_processing_succeeded");
            }
            Err(WorkerError::Transient(msg)) => {
                tracing::warn!(error = %msg, "transient_error");
                let _ = self.consumer.release(vec![lock_token]).await;
            }
            Err(WorkerError::Permanent(msg)) => {
                tracing::error!(error = %msg, "permanent_error");
                self.handler.handle_failure(&event_data, &msg).await;
                let _ = self.consumer.acknowledge(vec![lock_token]).await;
            }
        }
    }
}
