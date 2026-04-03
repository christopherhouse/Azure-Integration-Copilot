//! Event Grid Namespace pull-delivery and publish clients.

pub mod consumer;
pub mod publisher;

pub use consumer::EventGridConsumer;
pub use publisher::EventGridPublisher;
