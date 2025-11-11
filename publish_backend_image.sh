#!/usr/bin/env bash
set -euo pipefail

# Registry settings can be overridden by exporting REGISTRY, IMAGE_NAME, or IMAGE_TAG.
REGISTRY=${REGISTRY:-mcpschedule.azurecr.io}
IMAGE_NAME=${IMAGE_NAME:-mcp-schedule-server}
IMAGE_TAG=${IMAGE_TAG:-latest}
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}" && pwd)
BACKEND_DIR="${REPO_ROOT}/"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker CLI not found in PATH." >&2
  exit 1
fi

if [ ! -d "${BACKEND_DIR}" ]; then
  echo "Backend directory not found at ${BACKEND_DIR}" >&2
  exit 1
fi

cat <<EOF
Building backend image:
  Registry : ${REGISTRY}
  Image    : ${IMAGE_NAME}
  Tag      : ${IMAGE_TAG}
  Context  : ${BACKEND_DIR}
EOF

# Ensure you are logged in (e.g., az acr login --name "${REGISTRY%%.*}") before running this script.
docker build \
  --file "${BACKEND_DIR}/Dockerfile" \
  --target production \
  --tag "${FULL_IMAGE}" \
  "${BACKEND_DIR}"

docker push "${FULL_IMAGE}"

echo "Successfully pushed ${FULL_IMAGE}"