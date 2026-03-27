#!/usr/bin/env bash
# =============================================================================
# configure-cloudflare-dns.sh — Cloudflare DNS Record Configuration for AFD
# =============================================================================
# Registers Azure Front Door custom domain validation TXT records and CNAME
# records with Cloudflare DNS. Only creates records that don't already exist.
#
# Usage:
#   ./configure-cloudflare-dns.sh \
#     --profile-name <afd-profile-name> \
#     --resource-group <azure-resource-group> \
#     --cloudflare-zone-id <cloudflare-dns-zone-id> \
#     --cloudflare-api-key <cloudflare-api-token> \
#     --domains "cd-frontend,cd-backend,cd-pubsub" \
#     --endpoints "frontend.azurefd.net,backend.azurefd.net,pubsub.azurefd.net"
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
  echo -e "  ${CYAN}${BOLD}🌐 Cloudflare DNS Configuration for Azure Front Door${NC}"
  echo -e "  ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e ""
}

# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
PROFILE_NAME=""
RESOURCE_GROUP=""
CF_ZONE_ID=""
CF_API_KEY=""
DOMAINS_CSV=""
ENDPOINTS_CSV=""

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case $1 in
    --profile-name)       PROFILE_NAME="$2";    shift 2 ;;
    --resource-group)     RESOURCE_GROUP="$2";   shift 2 ;;
    --cloudflare-zone-id) CF_ZONE_ID="$2";       shift 2 ;;
    --cloudflare-api-key) CF_API_KEY="$2";       shift 2 ;;
    --domains)            DOMAINS_CSV="$2";      shift 2 ;;
    --endpoints)          ENDPOINTS_CSV="$2";    shift 2 ;;
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
[[ -z "${PROFILE_NAME}" ]]   && MISSING+=("--profile-name")
[[ -z "${RESOURCE_GROUP}" ]] && MISSING+=("--resource-group")
[[ -z "${CF_ZONE_ID}" ]]     && MISSING+=("--cloudflare-zone-id")
[[ -z "${CF_API_KEY}" ]]     && MISSING+=("--cloudflare-api-key")
[[ -z "${DOMAINS_CSV}" ]]    && MISSING+=("--domains")
[[ -z "${ENDPOINTS_CSV}" ]]  && MISSING+=("--endpoints")

if [[ ${#MISSING[@]} -gt 0 ]]; then
  log_error "Missing required parameters: ${MISSING[*]}"
  exit 1
fi

# Validate zone ID format (must be a 32-character lowercase hex string)
if [[ ! "${CF_ZONE_ID}" =~ ^[0-9a-f]{32}$ ]]; then
  log_error "Invalid Cloudflare zone ID: expected a 32-character hex string."
  log_error "You may have passed a zone name instead of a zone ID."
  log_error "Find your zone ID in the Cloudflare dashboard under the zone's Overview page."
  exit 1
fi

IFS=',' read -ra DOMAINS <<< "${DOMAINS_CSV}"
IFS=',' read -ra ENDPOINTS <<< "${ENDPOINTS_CSV}"

if [[ ${#DOMAINS[@]} -ne ${#ENDPOINTS[@]} ]]; then
  log_error "Number of domains (${#DOMAINS[@]}) must match number of endpoints (${#ENDPOINTS[@]})"
  exit 1
fi

CF_API="https://api.cloudflare.com/client/v4"

# ---------------------------------------------------------------------------
# Cloudflare API helpers
# ---------------------------------------------------------------------------

# Check if a DNS record of a given type and name already exists.
# Returns 0 (true) if it exists, 1 (false) otherwise.
cf_record_exists() {
  local RECORD_TYPE="$1"
  local RECORD_NAME="$2"

  local RESPONSE
  RESPONSE=$(curl -s -X GET \
    "${CF_API}/zones/${CF_ZONE_ID}/dns_records?type=${RECORD_TYPE}&name=${RECORD_NAME}" \
    -H "Authorization: Bearer ${CF_API_KEY}" \
    -H "Content-Type: application/json")

  local COUNT
  COUNT=$(echo "${RESPONSE}" | jq -r '.result | length')
  [[ "${COUNT}" -gt 0 ]]
}

# Create a DNS record in Cloudflare. Proxied is disabled by default
# (required for AFD domain validation and Private Link origins).
cf_create_record() {
  local RECORD_TYPE="$1"
  local RECORD_NAME="$2"
  local RECORD_CONTENT="$3"

  local RESPONSE
  RESPONSE=$(curl -s -X POST \
    "${CF_API}/zones/${CF_ZONE_ID}/dns_records" \
    -H "Authorization: Bearer ${CF_API_KEY}" \
    -H "Content-Type: application/json" \
    --data "{\"type\":\"${RECORD_TYPE}\",\"name\":\"${RECORD_NAME}\",\"content\":\"${RECORD_CONTENT}\",\"ttl\":1,\"proxied\":false}")

  local SUCCESS
  SUCCESS=$(echo "${RESPONSE}" | jq -r '.success')

  if [[ "${SUCCESS}" != "true" ]]; then
    local ERRORS
    ERRORS=$(echo "${RESPONSE}" | jq -r '.errors')
    log_error "Failed to create ${RECORD_TYPE} record for ${RECORD_NAME}: ${ERRORS}"
    return 1
  fi

  return 0
}

# ---------------------------------------------------------------------------
# Process each custom domain
# ---------------------------------------------------------------------------
ERRORS_FOUND=0

for i in "${!DOMAINS[@]}"; do
  DOMAIN_NAME="${DOMAINS[$i]}"
  CNAME_TARGET="${ENDPOINTS[$i]}"

  log_step "Processing custom domain: ${DOMAIN_NAME}"

  # Query AFD for domain hostname and validation token
  DOMAIN_INFO=$(az afd custom-domain show \
    --profile-name "${PROFILE_NAME}" \
    --resource-group "${RESOURCE_GROUP}" \
    --custom-domain-name "${DOMAIN_NAME}" \
    --query '{hostname: hostName, validationToken: validationProperties.validationToken}' \
    --output json)

  HOSTNAME=$(echo "${DOMAIN_INFO}" | jq -r '.hostname')
  TOKEN=$(echo "${DOMAIN_INFO}" | jq -r '.validationToken // empty')

  log_detail "Hostname    : ${HOSTNAME}"
  log_detail "CNAME target: ${CNAME_TARGET}"

  # --- TXT validation record ---
  if [[ -n "${TOKEN}" ]]; then
    TXT_NAME="_dnsauth.${HOSTNAME}"
    log_detail "Validation token found"

    if cf_record_exists "TXT" "${TXT_NAME}"; then
      log_info "TXT record already exists: ${TXT_NAME} — skipping"
    else
      if cf_create_record "TXT" "${TXT_NAME}" "${TOKEN}"; then
        log_success "Created TXT record: ${TXT_NAME}"
      else
        ERRORS_FOUND=1
      fi
    fi
  else
    log_info "No validation token for ${HOSTNAME} — domain may already be validated"
  fi

  # --- CNAME record ---
  if cf_record_exists "CNAME" "${HOSTNAME}"; then
    log_info "CNAME record already exists: ${HOSTNAME} — skipping"
  else
    if cf_create_record "CNAME" "${HOSTNAME}" "${CNAME_TARGET}"; then
      log_success "Created CNAME record: ${HOSTNAME} → ${CNAME_TARGET}"
    else
      ERRORS_FOUND=1
    fi
  fi

  echo ""
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
if [[ "${ERRORS_FOUND}" -eq 0 ]]; then
  echo -e "  ${GREEN}${BOLD}✅ Cloudflare DNS configuration complete${NC}"
else
  echo -e "  ${YELLOW}${BOLD}⚠️  Cloudflare DNS configuration completed with errors${NC}"
  exit 1
fi
echo -e ""
