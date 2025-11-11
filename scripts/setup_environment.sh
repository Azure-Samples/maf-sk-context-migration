#!/usr/bin/env bash
# Set up the local environment for the Microsoft Agent Framework workflow demo.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REQUIRED_MAJOR=3
REQUIRED_MINOR=13
VENV_DIR="${PROJECT_ROOT}/.venv"
REPO_NAME="maf-sk-context-migration"

log() {
  printf '[setup] %s\n' "$*"
}

fail() {
  printf '[setup][error] %s\n' "$*" >&2
  exit 1
}

ensure_python() {
  if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    fail "Python executable '${PYTHON_BIN}' not found. Set PYTHON_BIN or install Python ${REQUIRED_MAJOR}.${REQUIRED_MINOR}."
  fi

  local version
  version="$(${PYTHON_BIN} -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  local major minor
  major="${version%%.*}"
  minor="${version#${major}.}"
  minor="${minor%%.*}"

  if [[ "${major}" -lt ${REQUIRED_MAJOR} ]] || ([[ "${major}" -eq ${REQUIRED_MAJOR} ]] && [[ "${minor}" -lt ${REQUIRED_MINOR} ]]); then
    fail "Python ${version} detected. This project requires >= ${REQUIRED_MAJOR}.${REQUIRED_MINOR}."
  fi

  log "Python ${version} detected."
}

create_virtualenv() {
  if [[ ! -d "${VENV_DIR}" ]]; then
    log "Creating virtual environment at ${VENV_DIR}."
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  else
    log "Reusing existing virtual environment at ${VENV_DIR}."
  fi
}

activate_virtualenv() {
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  log "Virtual environment activated ($(python --version 2>&1))."
}

install_dependencies() {
  log "Upgrading pip and installing project dependencies."
  python -m pip install --upgrade pip
  python -m pip install -e "${PROJECT_ROOT}[dev]"
}

check_azure_cli() {
  if ! command -v az >/dev/null 2>&1; then
    log "Azure CLI not found. Install from https://learn.microsoft.com/cli/azure/install-azure-cli."
    return
  fi

  if ! az account show >/dev/null 2>&1; then
    log "Azure CLI detected but not authenticated. Run 'az login' before executing the workflows."
  else
    log "Azure CLI authenticated."
  fi
}

validate_env_vars() {
  local missing=()
  local required=(
    "AZURE_AI_PROJECT_ENDPOINT"
    "AZURE_AI_MODEL_DEPLOYMENT_NAME"
  )

  for var in "${required[@]}"; do
    if [[ -z "${!var-}" ]]; then
      missing+=("${var}")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    log "Missing required environment variables: ${missing[*]}"
    log "Update your shell profile or export them before running the demo."
  else
    log "All required Azure AI environment variables are set."
  fi

  local optional=("WORKFORCE_MCP_ENDPOINT")
  for var in "${optional[@]}"; do
    if [[ -z "${!var-}" ]]; then
      log "Optional environment variable ${var} is not set. Falling back to default endpoints."
    fi
  done
}

summarise() {
  log "Environment configuration complete for ${REPO_NAME}."
  log "Next steps:"
  log "  1. Ensure the MCP server is running (uvicorn mcp_server.main:app --reload)."
  log "  2. Configure Azure AI credentials (az login + env vars)."
  log "  3. Run 'python src/maf_workflow/agents.py' from the project root."
}

main() {
  cd "${PROJECT_ROOT}"
  log "Initialising environment for ${REPO_NAME} in ${PROJECT_ROOT}."
  ensure_python
  create_virtualenv
  activate_virtualenv
  install_dependencies
  check_azure_cli
  validate_env_vars
  summarise
}

main "$@"
