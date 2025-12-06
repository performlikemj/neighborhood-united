#!/usr/bin/env bash
set -euo pipefail

# Deploy the React frontend to Azure Container Apps via ACR build.
# Usage:
#   ./scripts/deploy_frontend.sh
#   ./scripts/deploy_frontend.sh --api-base https://hoodunited.org --tag $(date +%s)
#   ./scripts/deploy_frontend.sh --registry sautairegistry --resource-group sautAI --app sautai-react-westus2

REGISTRY="sautairegistry"
RESOURCE_GROUP="sautAI"
APP_NAME="sautai-react-westus2"
IMAGE_NAME="sautai-react-frontend"
API_BASE="https://hoodunited.org"
TAG="$(date +%Y%m%d%H%M%S)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry) REGISTRY="$2"; shift 2 ;;
    --resource-group|--rg) RESOURCE_GROUP="$2"; shift 2 ;;
    --app|--app-name) APP_NAME="$2"; shift 2 ;;
    --image|--image-name) IMAGE_NAME="$2"; shift 2 ;;
    --api-base) API_BASE="$2"; shift 2 ;;
    --tag) TAG="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--registry REG] [--resource-group RG] [--app APP] [--image NAME] [--api-base URL] [--tag TAG]"; exit 0 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# Resolve repo root and Dockerfile paths based on this script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKERFILE="$ROOT_DIR/frontend/Dockerfile"
BUILD_CONTEXT="$ROOT_DIR/frontend"

# Ensure az is logged in
az account show >/dev/null 2>&1 || { echo "Please run: az login"; exit 1; }

# Resolve ACR login server
LOGIN_SERVER="$(az acr show -n "$REGISTRY" -g "$RESOURCE_GROUP" --query loginServer -o tsv)"
if [[ -z "$LOGIN_SERVER" ]]; then
  echo "Failed to resolve ACR login server for registry: $REGISTRY" >&2
  exit 1
fi

# Build and push image (tagged with provided TAG and latest)
echo "Building image in ACR: $LOGIN_SERVER/$IMAGE_NAME:$TAG (API_BASE=$API_BASE)"
echo "Using Dockerfile: $DOCKERFILE"
echo "Build context:    $BUILD_CONTEXT"
az acr build \
  --registry "$REGISTRY" \
  --image "$IMAGE_NAME:$TAG" \
  --image "$IMAGE_NAME:latest" \
  --build-arg VITE_API_BASE="$API_BASE" \
  -f "$DOCKERFILE" \
  "$BUILD_CONTEXT"

# Roll the Container App to the new image tag
FULL_IMAGE="$LOGIN_SERVER/$IMAGE_NAME:$TAG"
echo "Updating Container App $APP_NAME to image: $FULL_IMAGE"
az containerapp update -n "$APP_NAME" -g "$RESOURCE_GROUP" --image "$FULL_IMAGE" -o table

# Show current FQDN
FQDN="$(az containerapp show -n "$APP_NAME" -g "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv)"
echo "Done. App is updating. FQDN: https://$FQDN/"
echo "Image: $FULL_IMAGE"
