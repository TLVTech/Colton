#!/usr/bin/env bash
set -euo pipefail

# ─── Configuration ──────────────────────────────────────────────────────────────
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="011528292014"
ECR_REPO="colton-ingestion"
IMAGE_TAG="all-scrapers-test"  
CLUSTER_NAME="colton-ingestion-cluster"
SERVICE_NAME="colton-ingestion-service"
TASKDEF_FILE="taskdef.json"
CONTAINER_NAME="colton-ingestion-container"

# ─── Step 1: Prune Docker Images ────────────────────────────────────────────────
echo "🧹 Pruning old Docker images and build cache..."
docker system prune -af

# ─── Step 2: Build Docker Image ────────────────────────────────────────────────
echo "🛠  Building Docker image: ${ECR_REPO}:${IMAGE_TAG}"
docker build -t "${ECR_REPO}:${IMAGE_TAG}" .

# ─── Step 3: Login, Tag, and Push to ECR ───────────────────────────────────────
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"
echo "🔑 Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "🏷  Tagging image as ${ECR_URI}"
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${ECR_URI}"

echo "🚀 Pushing image to ECR"
docker push "${ECR_URI}"

# ─── Step 4: Clean up old ECS service/tasks (optional) ─────────────────────────
# Only delete/recreate service if needed. Comment out if you want to keep service persistent.
echo "🔍 Checking if ECS service exists..."
SERVICE_ARN=$(aws ecs list-services --cluster "$CLUSTER_NAME" --query "serviceArns[?contains(@, '$SERVICE_NAME')]" --output text)
if [[ -n "$SERVICE_ARN" ]]; then
    echo "🛑 Deleting existing ECS service $SERVICE_NAME..."
    aws ecs update-service --cluster "$CLUSTER_NAME" --service "$SERVICE_NAME" --desired-count 0 || true
    sleep 10
    aws ecs delete-service --cluster "$CLUSTER_NAME" --service "$SERVICE_NAME" --force || true
    sleep 10
fi

echo "🧹 Stopping and deleting old tasks (if any)..."
TASK_ARN_LIST=$(aws ecs list-tasks --cluster "$CLUSTER_NAME" --query "taskArns[]" --output text)
for TASK_ARN in $TASK_ARN_LIST; do
    echo "  -> Stopping task $TASK_ARN"
    aws ecs stop-task --cluster "$CLUSTER_NAME" --task "$TASK_ARN"
done

# ─── Step 5: Register New Task Definition ──────────────────────────────────────
echo "📝 Registering new ECS task definition from $TASKDEF_FILE..."
aws ecs register-task-definition --cli-input-json file://$TASKDEF_FILE --region "$AWS_REGION"
NEW_REV=$(aws ecs list-task-definitions --family-prefix colton-ingestion-task --sort DESC --region "$AWS_REGION" --query "taskDefinitionArns[0]" --output text | awk -F':' '{print $NF}')
echo "🔄 New task definition revision: $NEW_REV"

# ─── Step 6: Create/Update ECS Service ─────────────────────────────────────────
echo "🔄 (Re)creating ECS service $SERVICE_NAME..."
aws ecs create-service --cluster "$CLUSTER_NAME" \
    --service-name "$SERVICE_NAME" \
    --task-definition "colton-ingestion-task:$NEW_REV" \
    --launch-type FARGATE \
    --desired-count 0 \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-0e9fd8c7e91199564],securityGroups=[sg-014f65acd7949ae7b],assignPublicIp=ENABLED}" \
    --region "$AWS_REGION" \
    --output text || \
aws ecs update-service --cluster "$CLUSTER_NAME" \
    --service "$SERVICE_NAME" \
    --task-definition "colton-ingestion-task:$NEW_REV" \
    --desired-count 0 \
    --region "$AWS_REGION"

# ─── Step 7: Run One-Off Manual Task ───────────────────────────────────────────
echo "🧪 Running a one-off ECS Fargate task for test purposes..."
aws ecs run-task \
    --cluster "$CLUSTER_NAME" \
    --launch-type FARGATE \
    --task-definition "colton-ingestion-task:$NEW_REV" \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-0e9fd8c7e91199564],securityGroups=[sg-014f65acd7949ae7b],assignPublicIp=ENABLED}" \
    --count 1

echo "✅ Deployment complete!"
# ─── End of Script ─────────────────────────────────────────────────────────────
echo "🚀 Your service is now running with the latest image."



# ---- Wait for the just-started task to STOP -------------------------------------
echo "⏳ Waiting for the ECS task to complete..."

# Start task and capture the Task ARN
TASK_ARN=$(aws ecs run-task \
    --cluster "$CLUSTER_NAME" \
    --launch-type FARGATE \
    --task-definition "colton-ingestion-task:$NEW_REV" \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-0e9fd8c7e91199564],securityGroups=[sg-014f65acd7949ae7b],assignPublicIp=ENABLED}" \
    --count 1 \
    --query 'tasks[0].taskArn' --output text)

echo "Task started: $TASK_ARN"

# Wait for it to stop
while : ; do
    STATUS=$(aws ecs describe-tasks --cluster "$CLUSTER_NAME" --tasks "$TASK_ARN" --query 'tasks[0].lastStatus' --output text)
    echo "  → Task status: $STATUS"
    if [[ "$STATUS" == "STOPPED" ]]; then
        break
    fi
    sleep 300
done

echo "✅ Task completed."

# ---- Now fetch the logs and save to a file --------------------------------------
LOG_GROUP='//ecs/colton-ingestion'
LOG_STREAM=$(aws logs describe-log-streams \
    --log-group-name "$LOG_GROUP" \
    --order-by LastEventTime --descending \
    --limit 1 \
    --query 'logStreams[0].logStreamName' --output text)

if [[ "$LOG_STREAM" != "None" ]]; then
    LOGFILE="ecs-task-logs-$(date +%Y%m%d-%H%M%S).txt"
    echo "📜 Fetching the latest logs from CloudWatch and saving to $LOGFILE:"
    aws logs get-log-events \
        --log-group-name "$LOG_GROUP" \
        --log-stream-name "$LOG_STREAM" \
        --limit 1000 --output text | grep -v "^PRE" | cut -f2- | tee "$LOGFILE"
    echo "📝 Logs saved to $LOGFILE"
else
    echo "⚠️  No log stream found for the latest task."
fi
