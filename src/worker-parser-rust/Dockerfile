# =============================================================================
# Multi-stage Dockerfile for integrisight-worker-parser-rust
# =============================================================================
# Stage 1: Build the Rust binary with all dependencies
# Stage 2: Minimal runtime image with just the compiled binary
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1 — Builder
# ---------------------------------------------------------------------------
FROM rust:1.86-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy manifests first for dependency caching
COPY Cargo.toml Cargo.lock ./

# Create a dummy main.rs to build dependencies (layer caching)
RUN mkdir src && \
    echo 'fn main() { println!("dummy"); }' > src/main.rs && \
    echo 'pub mod models; pub mod parsers; pub mod azure; pub mod config; pub mod event_types; pub mod worker;' > src/lib.rs && \
    mkdir -p src/parsers src/azure/event_grid src/worker && \
    touch src/models.rs src/config.rs src/event_types.rs && \
    touch src/parsers/mod.rs src/parsers/logic_app.rs src/parsers/openapi.rs src/parsers/apim_policy.rs && \
    touch src/azure/mod.rs src/azure/credential.rs src/azure/blob.rs src/azure/cosmos.rs && \
    touch src/azure/event_grid/mod.rs src/azure/event_grid/consumer.rs src/azure/event_grid/publisher.rs && \
    touch src/worker/mod.rs src/worker/base.rs src/worker/handler.rs && \
    cargo build --release 2>/dev/null || true && \
    rm -rf src

# Copy actual source code
COPY src/ src/

# Build the real binary
RUN cargo build --release

# ---------------------------------------------------------------------------
# Stage 2 — Runtime
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 worker && \
    useradd --uid 1000 --gid worker --shell /bin/false worker

WORKDIR /app

COPY --from=builder /build/target/release/integrisight-worker-parser-rust /app/worker

RUN chown -R worker:worker /app

USER worker

ENV RUST_LOG=info

CMD ["/app/worker"]
