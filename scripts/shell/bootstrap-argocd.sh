#!/usr/bin/env bash
set -euo pipefail

# =========================
# Script metadata
# =========================

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ROOT_APPLICATION_FILE="${REPO_ROOT}/platform/bootstrap/root-application.yaml"

# =========================
# Argo CD configuration
# =========================

ARGOCD_NAMESPACE="argocd"
ARGOCD_VERSION="v3.2.0"
ARGOCD_INSTALL_URL="https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"

# =========================
# Runtime defaults
# =========================

FORCE_REINSTALL="false"
BOOTSTRAP_ROOT_APP="false"
ROLLOUT_TIMEOUT="300s"
PULUMI_STACK="prd"
INFRA_CONFIG_FILE=""
DEFAULT_KUBECONFIG="${HOME}/.kube/config"

# =========================
# Logging helpers
# =========================

capitalize_first() {
  sed 's/^./\U&/'
}

log() {
  local msg
  msg="$(printf '%s' "$*" | capitalize_first)"
  printf '[%s] %s\n' "$SCRIPT_NAME" "$msg"
}

fail() {
  local msg
  msg="$(printf '%s' "$*" | capitalize_first)"
  printf '[%s] ERROR: %s\n' "$SCRIPT_NAME" "$msg" >&2
  exit 1
}

log_multiline() {
  local line
  while IFS= read -r line; do
    log "$line"
  done
}

# =========================
# Argument parsing
# =========================

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [options]

Options:
  --bootstrap-root-app  Apply the Argo CD root application
  --force-reinstall     Re-apply the Argo CD install manifest even if Argo CD exists
  --timeout VALUE       Rollout timeout for argocd-server (e.g. 300s, 10m, default: 300s)
  --stack VALUE         Pulumi stack name used to read infra/Pulumi.<stack>.yaml (default: prd)
  -h, --help            Show this help
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --bootstrap-root-app)
        BOOTSTRAP_ROOT_APP="true"
        shift
        ;;
      --force-reinstall)
        FORCE_REINSTALL="true"
        shift
        ;;
      --timeout)
        [[ $# -ge 2 ]] || fail "Missing value for --timeout"
        ROLLOUT_TIMEOUT="$2"
        shift 2
        ;;
      --stack)
        [[ $# -ge 2 ]] || fail "Missing value for --stack"
        PULUMI_STACK="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown argument: $1"
        ;;
    esac
  done
}

# =========================
# Utility helpers
# =========================

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

namespace_exists() {
  kubectl get namespace "$ARGOCD_NAMESPACE" >/dev/null 2>&1
}

argocd_installed() {
  kubectl get deployment argocd-server -n "$ARGOCD_NAMESPACE" >/dev/null 2>&1
}

# =========================
# Core functions
# =========================

set_working_directory() {
  local start_dir
  start_dir="$(pwd)"
  log "Starting in directory: ${start_dir}"
  cd "$REPO_ROOT"
  log "Working directory: $REPO_ROOT"
}

set_kubeconfig() {
  if [[ -n "${KUBECONFIG:-}" ]]; then
    [[ -f "$KUBECONFIG" ]] || fail "KUBECONFIG file not found: $KUBECONFIG"
    [[ -r "$KUBECONFIG" ]] || fail "KUBECONFIG file is not readable: $KUBECONFIG"
    log "Using kubeconfig from KUBECONFIG: ${KUBECONFIG}"
    return
  fi
  if [[ -f "$DEFAULT_KUBECONFIG" ]]; then
    export KUBECONFIG="$DEFAULT_KUBECONFIG"
    log "Using default kubeconfig: ${KUBECONFIG}"
    return
  fi
  fail "KUBECONFIG is not set and default kubeconfig was not found: ${DEFAULT_KUBECONFIG}"
}

set_infra_config_file() {
  INFRA_CONFIG_FILE="${REPO_ROOT}/infra/Pulumi.${PULUMI_STACK}.yaml"
  log "Using infrastructure config: ${INFRA_CONFIG_FILE}"
}

check_requirements() {
  log "Checking requirements"
  require_command kubectl
  require_command curl
}

check_cluster_access() {
  local context
  log "Checking Kubernetes cluster access"
  kubectl cluster-info >/dev/null
  context="$(kubectl config current-context)"
  log "Current Kubernetes context: ${context}"
}

get_expected_repository_url() {
  awk -F': ' '
    $1 ~ /^[[:space:]]*vultr-kubernetes-platform:repository_url$/ {
      print $2
      exit
    }
  ' "$INFRA_CONFIG_FILE"
}

is_git_repository_url() {
  local url="$1"
  [[ "$url" == *.git ]] && return 0
  [[ "$url" == git@* ]] && return 0
  [[ "$url" == ssh://git@* ]] && return 0
  return 1
}

check_repository_urls() {
  local expected_repository_url
  local mismatches=0
  local file
  local repo_url
  log "Checking Argo CD Git repository URLs"
  [[ -f "$INFRA_CONFIG_FILE" ]] || fail "Infrastructure config file not found: ${INFRA_CONFIG_FILE}"
  [[ -r "$INFRA_CONFIG_FILE" ]] || fail "Infrastructure config file is not readable: ${INFRA_CONFIG_FILE}"
  expected_repository_url="$(get_expected_repository_url)"
  [[ -n "$expected_repository_url" ]] || fail "repository_url is not set in ${INFRA_CONFIG_FILE}"
  while IFS= read -r file; do
    while IFS= read -r repo_url; do
      if ! is_git_repository_url "$repo_url"; then
        continue
      fi
      if [[ "$repo_url" != "$expected_repository_url" ]]; then
        log "Repository URL mismatch in ${file}"
        log "Expected: ${expected_repository_url}"
        log "Found:    ${repo_url}"
        mismatches=$((mismatches + 1))
      fi
    done < <(awk -F'repoURL:[[:space:]]*' '/repoURL:[[:space:]]*/ { print $2 }' "$file")
  done < <(find "${REPO_ROOT}/platform" -type f \( -name '*.yaml' -o -name '*.yml' \) | sort)
  if [[ "$mismatches" -gt 0 ]]; then
    fail "Found ${mismatches} Argo CD Git repository URL mismatch(es)"
  fi
  log "Argo CD Git repository URLs are consistent"
}

ensure_namespace() {
  if namespace_exists; then
    log "Namespace '${ARGOCD_NAMESPACE}' already exists"
  else
    log "Creating namespace: ${ARGOCD_NAMESPACE}"
    kubectl create namespace "$ARGOCD_NAMESPACE"
  fi
}

install_argocd() {
  if argocd_installed && [[ "$FORCE_REINSTALL" != "true" ]]; then
    log "Argo CD already installed in namespace '${ARGOCD_NAMESPACE}'"
  else
    if [[ "$FORCE_REINSTALL" == "true" ]]; then
      log "Force reinstall requested; applying Argo CD ${ARGOCD_VERSION} manifest"
    else
      log "Installing Argo CD ${ARGOCD_VERSION}"
    fi
    kubectl apply -n "$ARGOCD_NAMESPACE" --server-side --force-conflicts -f "$ARGOCD_INSTALL_URL"
  fi
}

wait_for_argocd() {
  local output
  log "Waiting for Argo CD server deployment (timeout: ${ROLLOUT_TIMEOUT})"
  if ! output=$(kubectl rollout status deployment/argocd-server -n "$ARGOCD_NAMESPACE" --timeout="$ROLLOUT_TIMEOUT" 2>&1); then
    printf '%s\n' "$output" | log_multiline
    fail "Rollout failed"
  fi
  printf '%s\n' "$output" | log_multiline
}

bootstrap_root_application() {
  local output
  if [[ "$BOOTSTRAP_ROOT_APP" != "true" ]]; then
    log "Skipping Argo CD root application bootstrap"
    return
  fi
  [[ -f "$ROOT_APPLICATION_FILE" ]] || fail "Root application file not found: ${ROOT_APPLICATION_FILE}"
  log "Applying Argo CD root application: ${ROOT_APPLICATION_FILE}"
  if ! output=$(kubectl apply -f "$ROOT_APPLICATION_FILE" 2>&1); then
    printf '%s\n' "$output" | log_multiline
    fail "Failed to apply Argo CD root application"
  fi
  printf '%s\n' "$output" | log_multiline
}

post_checks() {
  local output
  log "Checking Argo CD pods"
  output="$(kubectl get pods -n "$ARGOCD_NAMESPACE")"
  printf '%s\n' "$output" | log_multiline
  log "Argo CD bootstrap completed successfully"
}

print_next_steps() {
  log "Access UI with:"
  log "kubectl port-forward svc/argocd-server -n ${ARGOCD_NAMESPACE} 8080:443"
  log "Then open in your browser:"
  log "https://localhost:8080"
  log "Login with:"
  log "username: admin"
  if kubectl get secret argocd-initial-admin-secret -n "$ARGOCD_NAMESPACE" >/dev/null 2>&1; then
    log "Get initial password:"
    log "kubectl -n ${ARGOCD_NAMESPACE} get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo"
    log "After logging in, change the admin password and delete the initial secret:"
    log "kubectl -n ${ARGOCD_NAMESPACE} delete secret argocd-initial-admin-secret"
  else
    log "Initial admin password has already been removed"
  fi
}

# =========================
# Main
# =========================

main() {
  parse_args "$@"
  set_working_directory
  set_infra_config_file
  set_kubeconfig
  check_requirements
  check_cluster_access
  check_repository_urls
  ensure_namespace
  install_argocd
  wait_for_argocd
  bootstrap_root_application
  post_checks
  print_next_steps
}

main "$@"
exit 0