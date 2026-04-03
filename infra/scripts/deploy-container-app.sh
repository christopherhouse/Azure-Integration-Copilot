#!/usr/bin/env bash
# =============================================================================
# deploy-container-app.sh — Reusable Container App Deployment Script
# =============================================================================
# Deploys (creates or updates) a single Azure Container App.
#
# Usage:
#   ./deploy-container-app.sh \
#     --name <app-name> \
#     --resource-group <rg-name> \
#     --environment <cae-name> \
#     --image <full-image-reference> \
#     --target-port <port> \
#     --identity <managed-identity-resource-id> \
#     --registry-server <acr-login-server> \
#     --cpu <cpu-cores> \
#     --memory <memory> \
#     --min-replicas <min> \
#     --max-replicas <max> \
#     [--env-vars "KEY=value KEY2=value2"] \
#     [--ingress-external true|false]
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}ℹ${NC}  ${BOLD}$*${NC}"; }
log_success() { echo -e "${GREEN}✔${NC}  $*"; }
log_warn()    { echo -e "${YELLOW}⚠${NC}  $*"; }
log_error()   { echo -e "${RED}✖${NC}  $*" >&2; }
log_step()    { echo -e "${CYAN}▶${NC}  ${BOLD}$*${NC}"; }
log_detail()  { echo -e "   ${MAGENTA}→${NC} $*"; }

print_banner() {
  echo -e ""
  echo -e "  ${CYAN}${BOLD}🚀 Azure Container App Deployment${NC}"
  echo -e "  ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e ""
}

print_summary() {
  local INGRESS_LABEL="External"
  [[ "${INGRESS_EXTERNAL}" == "false" ]] && INGRESS_LABEL="Internal"

  echo -e "  ${BLUE}${BOLD}📦 Application${NC}"
  echo -e "  ${CYAN}├─${NC} ${BOLD}Name${NC}            ${GREEN}${APP_NAME}${NC}"
  echo -e "  ${CYAN}├─${NC} ${BOLD}Image${NC}           ${GREEN}${IMAGE}${NC}"
  echo -e "  ${CYAN}└─${NC} ${BOLD}Port${NC}            ${GREEN}${TARGET_PORT}${NC}"
  echo -e ""
  echo -e "  ${BLUE}${BOLD}☁️  Infrastructure${NC}"
  echo -e "  ${CYAN}├─${NC} ${BOLD}Resource Group${NC}  ${GREEN}${RESOURCE_GROUP}${NC}"
  echo -e "  ${CYAN}├─${NC} ${BOLD}Environment${NC}     ${GREEN}${ENVIRONMENT}${NC}"
  echo -e "  ${CYAN}└─${NC} ${BOLD}Registry${NC}        ${GREEN}${REGISTRY_SERVER}${NC}"
  echo -e ""
  echo -e "  ${BLUE}${BOLD}⚙️  Resources${NC}"
  echo -e "  ${CYAN}├─${NC} ${BOLD}CPU / Memory${NC}    ${GREEN}${CPU} cores · ${MEMORY}${NC}"
  echo -e "  ${CYAN}├─${NC} ${BOLD}Replicas${NC}        ${GREEN}${MIN_REPLICAS} → ${MAX_REPLICAS}${NC}"
  echo -e "  ${CYAN}└─${NC} ${BOLD}Ingress${NC}         ${GREEN}${INGRESS_LABEL}${NC}"
  echo -e ""
}

# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
APP_NAME=""
RESOURCE_GROUP=""
ENVIRONMENT=""
IMAGE=""
TARGET_PORT="80"
IDENTITY=""
REGISTRY_SERVER=""
CPU="0.25"
MEMORY="0.5Gi"
MIN_REPLICAS="0"
MAX_REPLICAS="10"
ENV_VARS=""
INGRESS_EXTERNAL="true"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case $1 in
    --name)             APP_NAME="$2";          shift 2 ;;
    --resource-group)   RESOURCE_GROUP="$2";    shift 2 ;;
    --environment)      ENVIRONMENT="$2";       shift 2 ;;
    --image)            IMAGE="$2";             shift 2 ;;
    --target-port)      TARGET_PORT="$2";       shift 2 ;;
    --identity)         IDENTITY="$2";          shift 2 ;;
    --registry-server)  REGISTRY_SERVER="$2";   shift 2 ;;
    --cpu)              CPU="$2";               shift 2 ;;
    --memory)           MEMORY="$2";            shift 2 ;;
    --min-replicas)     MIN_REPLICAS="$2";      shift 2 ;;
    --max-replicas)     MAX_REPLICAS="$2";      shift 2 ;;
    --env-vars)         ENV_VARS="$2";          shift 2 ;;
    --ingress-external) INGRESS_EXTERNAL="$2";  shift 2 ;;
    *)
      log_error "Unknown option: $1"
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Validate required parameters
# ---------------------------------------------------------------------------
print_banner

MISSING=()
[[ -z "${APP_NAME}" ]]       && MISSING+=("--name")
[[ -z "${RESOURCE_GROUP}" ]] && MISSING+=("--resource-group")
[[ -z "${ENVIRONMENT}" ]]    && MISSING+=("--environment")
[[ -z "${IMAGE}" ]]          && MISSING+=("--image")
[[ -z "${IDENTITY}" ]]       && MISSING+=("--identity")
[[ -z "${REGISTRY_SERVER}" ]] && MISSING+=("--registry-server")

if [[ ${#MISSING[@]} -gt 0 ]]; then
  log_error "Missing required parameters: ${MISSING[*]}"
  exit 1
fi

print_summary

# ---------------------------------------------------------------------------
# Check if the app already exists
# ---------------------------------------------------------------------------
log_step "Checking if Container App '${APP_NAME}' exists..."

if az containerapp show \
  --name "${APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --output none 2>/dev/null; then
  APP_EXISTS=true
  log_success "Container App '${APP_NAME}' found — will update"
else
  APP_EXISTS=false
  log_info "Container App '${APP_NAME}' not found — will create"
fi

# ---------------------------------------------------------------------------
# Build the az containerapp command
# ---------------------------------------------------------------------------
if [[ "${APP_EXISTS}" == "true" ]]; then
  log_step "Updating Container App '${APP_NAME}'..."

  # Ensure the user-assigned managed identity is (still) attached to the app.
  # `az containerapp update` does not accept --user-assigned, so we use the
  # dedicated identity command before updating the container image/config.
  log_detail "Ensuring managed identity is assigned..."
  if ! az containerapp identity assign \
    --name "${APP_NAME}" \
    --resource-group "${RESOURCE_GROUP}" \
    --user-assigned "${IDENTITY}" \
    --output none; then
    log_error "Failed to assign managed identity to '${APP_NAME}'"
    exit 1
  fi

  # Build update command
  UPDATE_CMD=(
    az containerapp update
    --name "${APP_NAME}"
    --resource-group "${RESOURCE_GROUP}"
    --image "${IMAGE}"
    --min-replicas "${MIN_REPLICAS}"
    --max-replicas "${MAX_REPLICAS}"
    --cpu "${CPU}"
    --memory "${MEMORY}"
    --registry-server "${REGISTRY_SERVER}"
    --registry-identity "${IDENTITY}"
  )

  if [[ -n "${ENV_VARS}" ]]; then
    UPDATE_CMD+=(--set-env-vars ${ENV_VARS})
  fi

  log_detail "Running: ${UPDATE_CMD[*]}"
  "${UPDATE_CMD[@]}" --output none

  log_success "Container App '${APP_NAME}' updated successfully"
else
  log_step "Creating Container App '${APP_NAME}'..."

  INGRESS_TYPE="external"
  if [[ "${INGRESS_EXTERNAL}" == "false" ]]; then
    INGRESS_TYPE="internal"
  fi

  CREATE_CMD=(
    az containerapp create
    --name "${APP_NAME}"
    --resource-group "${RESOURCE_GROUP}"
    --environment "${ENVIRONMENT}"
    --image "${IMAGE}"
    --target-port "${TARGET_PORT}"
    --ingress "${INGRESS_TYPE}"
    --transport http
    --cpu "${CPU}"
    --memory "${MEMORY}"
    --min-replicas "${MIN_REPLICAS}"
    --max-replicas "${MAX_REPLICAS}"
    --registry-server "${REGISTRY_SERVER}"
    --registry-identity "${IDENTITY}"
    --user-assigned "${IDENTITY}"
    --revisions-mode single
  )

  if [[ -n "${ENV_VARS}" ]]; then
    CREATE_CMD+=(--env-vars ${ENV_VARS})
  fi

  log_detail "Running: ${CREATE_CMD[*]}"
  "${CREATE_CMD[@]}" --output none

  log_success "Container App '${APP_NAME}' created successfully"
fi

# ---------------------------------------------------------------------------
# Verify deployment
# ---------------------------------------------------------------------------
log_step "Verifying deployment..."

FQDN=$(az containerapp show \
  --name "${APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv 2>/dev/null || echo "N/A")

PROVISIONING_STATE=$(az containerapp show \
  --name "${APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query "properties.provisioningState" \
  --output tsv 2>/dev/null || echo "Unknown")

RUNNING_STATUS=$(az containerapp show \
  --name "${APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query "properties.runningStatus" \
  --output tsv 2>/dev/null || echo "Unknown")

echo -e ""
echo -e "  ${GREEN}${BOLD}✅ Deployment Complete${NC}"
echo -e "  ${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e ""
echo -e "  ${CYAN}├─${NC} ${BOLD}App${NC}       ${GREEN}${APP_NAME}${NC}"
echo -e "  ${CYAN}├─${NC} ${BOLD}State${NC}     ${GREEN}${PROVISIONING_STATE}${NC}"
echo -e "  ${CYAN}├─${NC} ${BOLD}Status${NC}    ${GREEN}${RUNNING_STATUS}${NC}"
echo -e "  ${CYAN}├─${NC} ${BOLD}FQDN${NC}      ${GREEN}${FQDN}${NC}"
echo -e "  ${CYAN}└─${NC} ${BOLD}Image${NC}     ${GREEN}${IMAGE}${NC}"
echo -e ""
