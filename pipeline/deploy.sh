#!/usr/bin/env bash
set -euo pipefail

# ─── Configuration ──────────────────────────────────────────────────────────────

# AWS settings
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="011528292014"

# ECR repo and image tag
ECR_REPO="colton-ingestion"
IMAGE_TAG="latest"

# ECS settings
CLUSTER_NAME="colton-ingestion-cluster"
SERVICE_NAME="colton-ingestion-service"

# ─── Build the Docker image ────────────────────────────────────────────────────

echo "🛠  Building Docker image: ${ECR_REPO}:${IMAGE_TAG}"
docker build -t "${ECR_REPO}:${IMAGE_TAG}" .

# ─── Authenticate Docker to ECR ────────────────────────────────────────────────

echo "🔑 Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login \
      --username AWS \
      --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# ─── Ensure the ECR repository exists ──────────────────────────────────────────

if ! aws ecr describe-repositories \
       --repository-names "${ECR_REPO}" \
       --region "${AWS_REGION}" >/dev/null 2>&1; then
  echo "📦 Creating ECR repository: ${ECR_REPO}"
  aws ecr create-repository \
    --repository-name "${ECR_REPO}" \
    --region "${AWS_REGION}"
fi

# ─── Tag & push the image ─────────────────────────────────────────────────────

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"

echo "🏷  Tagging image as ${ECR_URI}"
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${ECR_URI}"

echo "🚀 Pushing image to ECR"
docker push "${ECR_URI}"

echo "📝 Registering new ECS task definition..."
aws ecs register-task-definition \
  --cli-input-json file://taskdef.json \
  --region "${AWS_REGION}"

NEW_REV=$(aws ecs list-task-definitions --family-prefix colton-ingestion-task --sort DESC --region "${AWS_REGION}" | grep colton-ingestion-task | head -1 | grep -o '[0-9]\+$')

echo "🔄 Updating ECS service to new revision $NEW_REV..."
aws ecs update-service \
  --cluster "${CLUSTER_NAME}" \
  --service "${SERVICE_NAME}" \
  --task-definition "colton-ingestion-task:${NEW_REV}" \
  --force-new-deployment \
  --region "${AWS_REGION}"

# ─── Trigger a new ECS deployment ─────────────────────────────────────────────

echo "🔄 Updating ECS service to force new deployment"
aws ecs update-service \
  --cluster "${CLUSTER_NAME}" \
  --service "${SERVICE_NAME}" \
  --force-new-deployment \
  --region "${AWS_REGION}"

echo "✅ Deployment initiated. ECS will pull the new image shortly."


#  run by using 
# chmod +x deploy.sh
# ./deploy.sh
