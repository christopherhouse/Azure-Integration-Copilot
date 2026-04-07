#!/usr/bin/env bash
# =============================================================================
# deploy-scan-gate-worker.sh — Deploy scan-gate Container App with ClamAV sidecar
# =============================================================================
# Deploys the scan-gate worker using a YAML template that includes a ClamAV
# sidecar container.  The generic deploy-container-app.sh script does not
# support sidecar containers, so this script handles YAML-based deployment.
#
# Usage:
#   ./deploy-scan-gate-worker.sh \
#     --name <app-name> \
#     --resource-group <rg-name> \
#     --environment <cae-name> \
#     --image <full-worker-image> \
#     --identity <managed-identity-resource-id> \
#     --registry-server <acr-login-server> \
#     --env-vars "KEY=value KEY2=value2"
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
BOLD='\033[1m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}ℹ${NC}  ${BOLD}$*${NC}"; }
log_success() { echo -e "${GREEN}✔${NC}  $*"; }
log_error()   { echo -e "${RED}✖${NC}  $*" >&2; }
log_step()    { echo -e "${CYAN}▶${NC}  ${BOLD}$*${NC}"; }

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
APP_NAME=""
RESOURCE_GROUP=""
ENVIRONMENT=""
IMAGE=""
IDENTITY=""
REGISTRY_SERVER=""
ENV_VARS=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --name)             APP_NAME="$2";          shift 2 ;;
    --resource-group)   RESOURCE_GROUP="$2";    shift 2 ;;
    --environment)      ENVIRONMENT="$2";       shift 2 ;;
    --image)            IMAGE="$2";             shift 2 ;;
    --identity)         IDENTITY="$2";          shift 2 ;;
    --registry-server)  REGISTRY_SERVER="$2";   shift 2 ;;
    --env-vars)         ENV_VARS="$2";          shift 2 ;;
    *)
      log_error "Unknown option: $1"
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Validate required parameters
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Resolve the Container Apps Environment resource ID
# ---------------------------------------------------------------------------
log_step "Resolving Container Apps Environment resource ID..."
ENVIRONMENT_ID=$(az containerapp env show \
  --name "${ENVIRONMENT}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query "id" --output tsv)

LOCATION=$(az containerapp env show \
  --name "${ENVIRONMENT}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query "location" --output tsv)

log_info "Environment ID: ${ENVIRONMENT_ID}"
log_info "Location: ${LOCATION}"

# ---------------------------------------------------------------------------
# Build environment variables YAML block
# ---------------------------------------------------------------------------
ENV_VARS_YAML=""
if [[ -n "${ENV_VARS}" ]]; then
  for pair in ${ENV_VARS}; do
    KEY="${pair%%=*}"
    VALUE="${pair#*=}"
    ENV_VARS_YAML+="          - name: ${KEY}"$'\n'
    ENV_VARS_YAML+="            value: \"${VALUE}\""$'\n'
  done
fi

# ---------------------------------------------------------------------------
# Prepare the YAML template
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_PATH="${SCRIPT_DIR}/../container-apps/worker-scan-gate.yaml"

if [[ ! -f "${TEMPLATE_PATH}" ]]; then
  log_error "YAML template not found at: ${TEMPLATE_PATH}"
  exit 1
fi

log_step "Preparing YAML deployment template..."
YAML_FILE=$(mktemp /tmp/scan-gate-deploy-XXXXXX.yaml)

# Replace placeholders in the template
sed \
  -e "s|__APP_NAME__|${APP_NAME}|g" \
  -e "s|__LOCATION__|${LOCATION}|g" \
  -e "s|__ENVIRONMENT_ID__|${ENVIRONMENT_ID}|g" \
  -e "s|__WORKER_IMAGE__|${IMAGE}|g" \
  -e "s|__IDENTITY_RESOURCE_ID__|${IDENTITY}|g" \
  -e "s|__REGISTRY_SERVER__|${REGISTRY_SERVER}|g" \
  "${TEMPLATE_PATH}" > "${YAML_FILE}"

# Inject environment variables into the YAML
if [[ -n "${ENV_VARS_YAML}" ]]; then
  # Write env block to a temp file, then use awk to replace the placeholder line.
  ENV_FILE=$(mktemp /tmp/scan-gate-env-XXXXXX.yaml)
  echo -n "${ENV_VARS_YAML}" > "${ENV_FILE}"
  # Replace the placeholder line with the env block contents (preserving indentation)
  awk -v envfile="${ENV_FILE}" '
    /^ *__ENV_VARS_YAML__/ {
      while ((getline line < envfile) > 0) print line
      next
    }
    { print }
  ' "${YAML_FILE}" > "${YAML_FILE}.tmp" && mv "${YAML_FILE}.tmp" "${YAML_FILE}"
  rm -f "${ENV_FILE}"
else
  # No env vars — remove the placeholder line entirely (env: with no items is valid)
  sed -i '/__ENV_VARS_YAML__/d' "${YAML_FILE}"
fi

log_info "Generated YAML:"
cat "${YAML_FILE}"

# ---------------------------------------------------------------------------
# Deploy using az containerapp create/update --yaml
# ---------------------------------------------------------------------------
log_step "Checking if Container App '${APP_NAME}' exists..."

if az containerapp show \
  --name "${APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --output none 2>/dev/null; then

  log_info "Container App '${APP_NAME}' found — updating with YAML..."

  # Ensure managed identity is still attached
  az containerapp identity assign \
    --name "${APP_NAME}" \
    --resource-group "${RESOURCE_GROUP}" \
    --user-assigned "${IDENTITY}" \
    --output none 2>/dev/null || true

  az containerapp update \
    --name "${APP_NAME}" \
    --resource-group "${RESOURCE_GROUP}" \
    --yaml "${YAML_FILE}" \
    --output none

  log_success "Container App '${APP_NAME}' updated with ClamAV sidecar"
else
  log_info "Container App '${APP_NAME}' not found — creating with YAML..."

  az containerapp create \
    --name "${APP_NAME}" \
    --resource-group "${RESOURCE_GROUP}" \
    --yaml "${YAML_FILE}" \
    --output none

  log_success "Container App '${APP_NAME}' created with ClamAV sidecar"
fi

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
rm -f "${YAML_FILE}"

# ---------------------------------------------------------------------------
# Verify deployment
# ---------------------------------------------------------------------------
log_step "Verifying deployment..."

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
echo -e "  ${GREEN}${BOLD}✅ Scan-Gate Deployment Complete${NC}"
echo -e "  ${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e ""
echo -e "  ${CYAN}├─${NC} ${BOLD}App${NC}        ${GREEN}${APP_NAME}${NC}"
echo -e "  ${CYAN}├─${NC} ${BOLD}State${NC}      ${GREEN}${PROVISIONING_STATE}${NC}"
echo -e "  ${CYAN}├─${NC} ${BOLD}Status${NC}     ${GREEN}${RUNNING_STATUS}${NC}"
echo -e "  ${CYAN}├─${NC} ${BOLD}Worker${NC}     ${GREEN}${IMAGE}${NC}"
echo -e "  ${CYAN}└─${NC} ${BOLD}Sidecar${NC}    ${GREEN}clamav/clamav:1.5.2 (SHA-pinned)${NC}"
echo -e ""
