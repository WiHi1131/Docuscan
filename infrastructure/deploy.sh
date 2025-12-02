#!/bin/bash

# DocuScan Deployment Script for Google Cloud Platform
# This script deploys the entire DocuScan infrastructure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"docuscan-project"}
REGION=${GCP_REGION:-"us-central1"}
API_SERVICE_NAME="docuscan-api"
WORKER_JOB_NAME="docuscan-worker"

echo -e "${GREEN}=== DocuScan Deployment ===${NC}"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Function to print step
print_step() {
    echo -e "${YELLOW}>>> $1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_step "Checking prerequisites..."
if ! command_exists gcloud; then
    echo -e "${RED}Error: gcloud CLI not found. Please install Google Cloud SDK.${NC}"
    exit 1
fi

if ! command_exists docker; then
    echo -e "${RED}Error: docker not found. Please install Docker.${NC}"
    exit 1
fi

# Set project
print_step "Setting GCP project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
print_step "Enabling required Google Cloud APIs..."
gcloud services enable \
    run.googleapis.com \
    sqladmin.googleapis.com \
    storage.googleapis.com \
    pubsub.googleapis.com \
    redis.googleapis.com \
    cloudbuild.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com

# Create Cloud Storage buckets
print_step "Creating Cloud Storage buckets..."
gsutil mb -l $REGION gs://docuscan-uploads-$PROJECT_ID/ 2>/dev/null || echo "Upload bucket already exists"
gsutil mb -l $REGION gs://docuscan-results-$PROJECT_ID/ 2>/dev/null || echo "Results bucket already exists"

# Create Pub/Sub topic and subscription
print_step "Creating Pub/Sub topic and subscription..."
gcloud pubsub topics create ocr-jobs 2>/dev/null || echo "Topic already exists"
gcloud pubsub subscriptions create ocr-jobs-sub \
    --topic=ocr-jobs \
    --ack-deadline=600 2>/dev/null || echo "Subscription already exists"

# Create Cloud SQL instance
print_step "Creating Cloud SQL instance (this may take several minutes)..."
gcloud sql instances create docuscan-db \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=$REGION \
    --root-password=ChangeMeInProduction \
    --database-flags=max_connections=100 2>/dev/null || echo "SQL instance already exists"

# Create database
print_step "Creating database..."
gcloud sql databases create docuscan \
    --instance=docuscan-db 2>/dev/null || echo "Database already exists"

# Create Memorystore Redis instance
print_step "Creating Memorystore Redis instance..."
gcloud redis instances create docuscan-cache \
    --size=1 \
    --region=$REGION \
    --tier=basic 2>/dev/null || echo "Redis instance already exists"

# Build and push API container
print_step "Building and pushing API container..."
gcloud builds submit \
    --tag gcr.io/$PROJECT_ID/$API_SERVICE_NAME \
    --file Dockerfile.api .

# Deploy API to Cloud Run
print_step "Deploying API to Cloud Run..."
gcloud run deploy $API_SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$API_SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID" \
    --add-cloudsql-instances $PROJECT_ID:$REGION:docuscan-db \
    --memory 512Mi \
    --cpu 1 \
    --max-instances 10

# Build and push Worker container
print_step "Building and pushing Worker container..."
gcloud builds submit \
    --tag gcr.io/$PROJECT_ID/$WORKER_JOB_NAME \
    --file Dockerfile.worker .

# Deploy Worker as Cloud Run Job
print_step "Deploying Worker as Cloud Run Job..."
gcloud run jobs create $WORKER_JOB_NAME \
    --image gcr.io/$PROJECT_ID/$WORKER_JOB_NAME \
    --region $REGION \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID" \
    --add-cloudsql-instances $PROJECT_ID:$REGION:docuscan-db \
    --memory 1Gi \
    --cpu 2 \
    --max-retries 3 \
    --task-timeout 600 2>/dev/null || echo "Job already exists"

# Get API URL
print_step "Getting API URL..."
API_URL=$(gcloud run services describe $API_SERVICE_NAME \
    --region $REGION \
    --format 'value(status.url)')

echo ""
echo -e "${GREEN}=== Deployment Complete! ===${NC}"
echo ""
echo "API URL: $API_URL"
echo ""
echo "Next steps:"
echo "1. Initialize database schema:"
echo "   curl -X POST $API_URL/admin/init-db"
echo ""
echo "2. Test the API:"
echo "   curl $API_URL/health"
echo ""
echo "3. Upload a document:"
echo "   curl -X POST -F 'file=@test.pdf' $API_URL/upload"
echo ""
echo "4. Configure Cloud Scheduler to trigger worker:"
echo "   gcloud scheduler jobs create pubsub worker-trigger \\"
echo "     --schedule='* * * * *' \\"
echo "     --topic=ocr-jobs \\"
echo "     --message-body='{\"trigger\":\"scheduler\"}'"
echo ""
