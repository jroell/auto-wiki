#!/usr/bin/env bash
set -euo pipefail
PROJECT="${PROJECT_ID:-vurvey-development}"
REGION="${REGION:-us-central1}"
API_IMAGE="gcr.io/${PROJECT}/wiki-api:latest"
WEB_IMAGE="gcr.io/${PROJECT}/wiki-web:latest"
API_SERVICE="wiki-api"
WEB_SERVICE="wiki-web"

# Build images locally (optional if using Cloud Build)
# docker build -f Dockerfile.backend -t ${API_IMAGE} .
# docker build -f Dockerfile.frontend -t ${WEB_IMAGE} .
# docker push ${API_IMAGE}
# docker push ${WEB_IMAGE}

# Deploy backend
BACKEND_ENV_VARS=(PORT=8001 PYTHONUNBUFFERED=1)
if [[ -n "${REDIS_URL:-}" ]]; then BACKEND_ENV_VARS+=(REDIS_URL=${REDIS_URL}); fi
if [[ -n "${MAX_JOB_WORKERS:-}" ]]; then BACKEND_ENV_VARS+=(MAX_JOB_WORKERS=${MAX_JOB_WORKERS}); fi
if [[ -n "${CACHE_BUCKET:-}" ]]; then BACKEND_ENV_VARS+=(CACHE_BUCKET=${CACHE_BUCKET}); fi
if [[ -n "${CACHE_PREFIX:-}" ]]; then BACKEND_ENV_VARS+=(CACHE_PREFIX=${CACHE_PREFIX}); fi

# Secrets (optional) - set envs directly or provide SECRET_* values to bind from Secret Manager
SECRET_FLAGS=()
if [[ -n "${SECRET_GOOGLE_API_KEY:-}" ]]; then
  SECRET_FLAGS+=(--set-secrets=GOOGLE_API_KEY=${SECRET_GOOGLE_API_KEY})
elif [[ -n "${GOOGLE_API_KEY:-}" ]]; then
  BACKEND_ENV_VARS+=(GOOGLE_API_KEY=${GOOGLE_API_KEY})
fi

if [[ -n "${SECRET_OPENAI_API_KEY:-}" ]]; then
  SECRET_FLAGS+=(--set-secrets=OPENAI_API_KEY=${SECRET_OPENAI_API_KEY})
elif [[ -n "${OPENAI_API_KEY:-}" ]]; then
  BACKEND_ENV_VARS+=(OPENAI_API_KEY=${OPENAI_API_KEY})
fi

if [[ -n "${SECRET_OPENROUTER_API_KEY:-}" ]]; then
  SECRET_FLAGS+=(--set-secrets=OPENROUTER_API_KEY=${SECRET_OPENROUTER_API_KEY})
elif [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
  BACKEND_ENV_VARS+=(OPENROUTER_API_KEY=${OPENROUTER_API_KEY})
fi

gcloud run deploy ${API_SERVICE} \
  --project=${PROJECT} \
  --region=${REGION} \
  --image=${API_IMAGE} \
  --port=8001 \
  --allow-unauthenticated \
  --set-env-vars="$(IFS=,; echo "${BACKEND_ENV_VARS[*]}")" \
  "${SECRET_FLAGS[@]}"

API_URL=$(gcloud run services describe ${API_SERVICE} --project=${PROJECT} --region=${REGION} --format='value(status.url)')

# Deploy frontend
gcloud run deploy ${WEB_SERVICE} \
  --project=${PROJECT} \
  --region=${REGION} \
  --image=${WEB_IMAGE} \
  --port=3000 \
  --allow-unauthenticated \
  --set-env-vars=PORT=3000 \
  --set-env-vars=PYTHON_BACKEND_HOST=${API_URL}

echo "Backend URL: ${API_URL}"
