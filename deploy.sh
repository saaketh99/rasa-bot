#!/bin/bash

# Variables
AWS_REGION="eu-north-1"
ACCOUNT_ID="644171585056"
CLUSTER_NAME="rasa-cluster"  # 👈 Your ECS cluster name here

REPOS=("rasa-frontend" "rasa-backend" "rasa-actions")

echo "🔐 Logging in to AWS ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

for REPO in "${REPOS[@]}"; do
    echo "🚀 Building and pushing $REPO..."

    if [ "$REPO" == "rasa-frontend" ]; then
        DOCKERFILE="frontend/frontend.dockerfile"
    elif [ "$REPO" == "rasa-backend" ]; then
        DOCKERFILE="Backend.dockerfile"
    else
        DOCKERFILE="actions/actions.dockerfile"
    fi

    docker build -f $DOCKERFILE -t $REPO .
    docker tag $REPO:latest ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/$REPO:latest
    docker push ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/$REPO:latest

    echo "🔄 Registering new task definition for $REPO..."

    # Fetch the current task definition
    TASK_DEF_JSON=$(aws ecs describe-task-definition \
        --task-definition $REPO \
        --region $AWS_REGION)

    # Create a new task definition JSON with updated image
    NEW_TASK_DEF=$(echo $TASK_DEF_JSON | jq --arg IMAGE "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/$REPO:latest" '
        .taskDefinition | {
            family: .family,
            containerDefinitions: (.containerDefinitions | map(.image = $IMAGE)),
            requiresCompatibilities,
            networkMode,
            cpu,
            memory,
            executionRoleArn,
            taskRoleArn
        }')

    # Register new task definition
    NEW_REVISION=$(aws ecs register-task-definition \
        --cli-input-json "$(echo $NEW_TASK_DEF)" \
        --region $AWS_REGION \
        --query 'taskDefinition.revision' --output text)

    echo "✅ Registered $REPO task definition revision: $NEW_REVISION"

    echo "📦 Updating ECS service for $REPO..."

    aws ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $REPO \
        --task-definition "$REPO:$NEW_REVISION" \
        --region $AWS_REGION

    echo "✅ Service $REPO updated to revision $NEW_REVISION"
done

echo "🎉 All services deployed and updated!"
