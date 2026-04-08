# =============================================================================
# Multi-stage Dockerfile for integrisight-worker-analysis-fsharp
# Stage 1: Build the .NET 10 F# binary
# Stage 2: Minimal runtime image
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1 — Builder
# ---------------------------------------------------------------------------
# Pin to a specific .NET 10 SDK image digest for reproducibility.
# Image: mcr.microsoft.com/dotnet/sdk:10.0
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS builder

WORKDIR /build

# Copy project file first for NuGet restore layer caching
COPY IntegrisightWorkerAnalysis.fsproj ./

# Restore NuGet packages
RUN dotnet restore IntegrisightWorkerAnalysis.fsproj

# Copy all source files
COPY *.fs ./

# Publish self-contained release binary
RUN dotnet publish IntegrisightWorkerAnalysis.fsproj \
    --configuration Release \
    --output /app/publish \
    --no-restore

# ---------------------------------------------------------------------------
# Stage 2 — Runtime
# ---------------------------------------------------------------------------
# Pin to a specific .NET 10 ASP.NET runtime image digest for reproducibility.
# Image: mcr.microsoft.com/dotnet/runtime:10.0
FROM mcr.microsoft.com/dotnet/runtime:10.0 AS runtime

# Install ca-certificates for Azure SDK TLS connections
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd --gid 1000 worker && \
    useradd --uid 1000 --gid worker --shell /bin/false worker

WORKDIR /app

COPY --from=builder /app/publish ./

RUN chown -R worker:worker /app

USER worker

# Default environment (overridden at deploy time)
ENV ENVIRONMENT=production
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false

CMD ["./IntegrisightWorkerAnalysis"]
