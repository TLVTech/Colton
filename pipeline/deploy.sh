#!/usr/bin/env bash
set -euo pipefail

# ─── Configuration ──────────────────────────────────────────────
SCRAPER_NAME="five_star"  # <--- CHANGE THIS for each run: fyda, five_star, jasper, ftlgr, shanes_equipment
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="011528292014"
ECR_REPO="colton-ingestion"
IMAGE_TAG="all-scrapers-test"  
CLUSTER_NAME="colton-ingestion-cluster"
TASKDEF_FILE="taskdef.json"
CONTAINER_NAME="colton-ingestion-container"
SUBNET="subnet-0e9fd8c7e91199564"
SECURITY_GROUP="sg-014f65acd7949ae7b"

# ─── Step 1: Build and Push Docker Image ───────────────────────
echo "🛠  Building Docker image: ${ECR_REPO}:${IMAGE_TAG}"
docker build -t "${ECR_REPO}:${IMAGE_TAG}" .

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"
echo "🔑 Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "🏷  Tagging image as ${ECR_URI}"
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${ECR_URI}"

echo "🚀 Pushing image to ECR"
docker push "${ECR_URI}"

# ─── Step 2: Register New Task Definition ──────────────────────
echo "📝 Registering new ECS task definition from $TASKDEF_FILE..."
aws ecs register-task-definition --cli-input-json file://$TASKDEF_FILE --region "$AWS_REGION"
NEW_REV=$(aws ecs list-task-definitions --family-prefix colton-ingestion-task --sort DESC --region "$AWS_REGION" --query "taskDefinitionArns[0]" --output text | awk -F':' '{print $NF}')
echo "🔄 New task definition revision: $NEW_REV"

# ─── Step 3: Run ECS Fargate Task for the Selected Scraper ─────
echo "🧪 Running a one-off ECS Fargate task for ${SCRAPER_NAME}..."
TASK_ARN=$(aws ecs run-task \
    --cluster "$CLUSTER_NAME" \
    --launch-type FARGATE \
    --task-definition "colton-ingestion-task:$NEW_REV" \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SECURITY_GROUP],assignPublicIp=ENABLED}" \
    --overrides "{\"containerOverrides\":[{\"name\":\"$CONTAINER_NAME\",\"environment\":[{\"name\":\"SCRAPER_NAME\",\"value\":\"$SCRAPER_NAME\"}]}]}" \
    --count 1 \
    --query 'tasks[0].taskArn' --output text)

echo "Task started: $TASK_ARN"

# ---- Wait for the just-started task to STOP -------------------------------------
echo "⏳ Waiting for the ECS task to complete..."
while : ; do
    STATUS=$(aws ecs describe-tasks --cluster "$CLUSTER_NAME" --tasks "$TASK_ARN" --query 'tasks[0].lastStatus' --output text)
    echo "  → Task status: $STATUS"
    if [[ "$STATUS" == "STOPPED" ]]; then
        break
    fi
    sleep 30
done

echo "✅ Task completed."

# ---- Fetch Logs from CloudWatch -----------------------------------------------
LOG_GROUP='/ecs/colton-ingestion'
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

echo "✅ Deployment complete!"
echo "🚀 Your single-scraper task ($SCRAPER_NAME) has run!"
