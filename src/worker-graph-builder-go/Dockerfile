# =============================================================================
# Multi-stage Dockerfile for integrisight-worker-graph-builder-go
# =============================================================================
# Stage 1: Build the Go binary
# Stage 2: Minimal runtime image
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1 — Builder
# golang 1.24.2 — https://hub.docker.com/_/golang/tags
# ---------------------------------------------------------------------------
FROM golang:1.24.2-bookworm AS builder

WORKDIR /build

# Copy module files first for dependency layer caching.
COPY go.mod go.sum ./
RUN go mod download

# Copy source and build.
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o worker .

# ---------------------------------------------------------------------------
# Stage 2 — Runtime
# debian:bookworm-slim — minimal image with ca-certificates
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user.
RUN groupadd --gid 1000 worker && \
    useradd --uid 1000 --gid worker --shell /bin/false --create-home worker

WORKDIR /app

COPY --from=builder /build/worker /app/worker

RUN chown -R worker:worker /app

USER worker

CMD ["/app/worker"]
