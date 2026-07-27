#!/bin/bash
set -e

if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI not installed."
    exit 1
fi

echo "Step 1: Initializing infrastructure with Terraform..."
terraform init
terraform apply -auto-approve

REGION="ap-southeast-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URL="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "Step 2: Logging into AWS ECR..."
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_URL}

echo "Step 3: Building and pushing Docker image..."
docker build -t newsrag-api .
docker tag newsrag-api:latest ${ECR_URL}/newsrag-api:latest
docker push ${ECR_URL}/newsrag-api:latest

echo "DONE! Deployed to AWS successfully."
