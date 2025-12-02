#!/bin/bash

# DocuScan API Usage Examples
# Demonstrates how to use the DocuScan API

API_URL=${API_URL:-"http://localhost:8080"}

echo "=== DocuScan API Examples ==="
echo "API URL: $API_URL"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print section
print_section() {
    echo -e "${BLUE}>>> $1${NC}"
}

# Function to print result
print_result() {
    echo -e "${GREEN}$1${NC}"
    echo ""
}

# 1. Health Check
print_section "1. Health Check"
echo "curl $API_URL/health"
curl -s $API_URL/health | jq '.'
print_result "✓ API is healthy"

# 2. Upload a PDF (you need to have a test.pdf file)
if [ -f "test.pdf" ]; then
    print_section "2. Upload PDF Document"
    echo "curl -X POST -F 'file=@test.pdf' $API_URL/upload"
    UPLOAD_RESPONSE=$(curl -s -X POST -F 'file=@test.pdf' $API_URL/upload)
    echo $UPLOAD_RESPONSE | jq '.'
    
    JOB_ID=$(echo $UPLOAD_RESPONSE | jq -r '.job_id')
    print_result "✓ Document uploaded with job_id: $JOB_ID"
    
    # 3. Check Job Status
    print_section "3. Check Job Status"
    echo "curl $API_URL/jobs/$JOB_ID"
    sleep 2  # Wait a bit for processing
    curl -s $API_URL/jobs/$JOB_ID | jq '.'
    print_result "✓ Job status retrieved"
    
    # 4. Wait for completion and get results
    print_section "4. Waiting for job to complete..."
    MAX_WAIT=60
    WAITED=0
    while [ $WAITED -lt $MAX_WAIT ]; do
        STATUS=$(curl -s $API_URL/jobs/$JOB_ID | jq -r '.status')
        echo "Status: $STATUS"
        
        if [ "$STATUS" == "completed" ]; then
            print_result "✓ Job completed!"
            break
        elif [ "$STATUS" == "failed" ]; then
            print_result "✗ Job failed"
            break
        fi
        
        sleep 5
        WAITED=$((WAITED + 5))
    done
    
    # 5. Get Results
    if [ "$STATUS" == "completed" ]; then
        print_section "5. Get OCR Results"
        echo "curl $API_URL/jobs/$JOB_ID/results"
        curl -s $API_URL/jobs/$JOB_ID/results | jq '.'
        print_result "✓ Results retrieved"
    fi
else
    echo "Note: test.pdf not found. Skipping upload examples."
    echo ""
fi

# 6. List All Jobs
print_section "6. List All Jobs"
echo "curl $API_URL/jobs?limit=5"
curl -s "$API_URL/jobs?limit=5" | jq '.'
print_result "✓ Jobs listed"

# 7. Search Documents
print_section "7. Search Documents"
echo "curl -X POST $API_URL/search -H 'Content-Type: application/json' -d '{\"query\": \"test\", \"limit\": 5}'"
curl -s -X POST $API_URL/search \
    -H "Content-Type: application/json" \
    -d '{"query": "test", "limit": 5}' | jq '.'
print_result "✓ Search completed"

# 8. Filter Jobs by Status
print_section "8. Filter Jobs by Status"
echo "curl $API_URL/jobs?status=completed&limit=10"
curl -s "$API_URL/jobs?status=completed&limit=10" | jq '.'
print_result "✓ Filtered jobs retrieved"

echo ""
echo "=== Examples Complete ==="
echo ""
echo "For interactive API documentation, visit:"
echo "  $API_URL/docs"
echo ""
