//! Azure service abstractions.
//!
//! Provides async clients for Azure Blob Storage, Cosmos DB, and Event Grid
//! using managed identity authentication via the IMDS endpoint.

pub mod blob;
pub mod cosmos;
pub mod credential;
pub mod event_grid;
