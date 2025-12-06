# DocuScan: A Distributed Cloud-Based OCR Service

## Overview
Welcome to DocuScan, our final project for the Datacenter Scale Computing class! This is a production-ready, event-driven OCR system to ingest user-uploaded images or PDFs, extract text asynchronously with Tesseract, persist results in a searchable PostgreSQL database, and scale automatically under load—all on Google Cloud Platform. DocuScan demonstrates key class concepts like loose coupling via Pub/Sub, fault tolerance through retries, and serverless elasticity with Cloud Run, handling bursts of 50-100 concurrent uploads per minute at minimal cost.

OCR converts visual text (e.g., from a PNG like "The Quick Brown Fox Jumps Over The Lazy Dog") into a Unicode UTF-8 encoded string, stored in Cloud SQL for full-text search. This repo contains the full codebase, deployment scripts, and tests. See our video for a walkthrough of the architecture and interactions.

## 🏗️ Architecture
DocuScan uses a microservices architecture:
```
User → API (Cloud Run) → Pub/Sub → Worker (Cloud Run Jobs) → Results
         ↓                                 ↓
    Cloud Storage                       Cloud SQL
         ↓                                 ↓
    Redis Cache ←─────────────────────────┘
```
- User uploads to FastAPI API, branching to GCS (blob), SQL (metadata), Pub/Sub (message).
- Scheduler triggers worker to pull, extract with Tesseract, update SQL/Redis.
- Queries return ranked results via API.

[Embed Diagram PNG Here: Figure 1: DocuScan Architecture—Event-Driven OCR Pipeline on GCP. Caption: Dashed arrows = async flows; VPC secures private access.]

## Components
### Software Components
- **FastAPI (Python 3.11)**: REST API for uploads/queries. Validates files, publishes to Pub/Sub, queries SQL/Redis.
- **Tesseract 5.5.0**: OCR engine. Converts images/PDFs to text strings.
- **pdf2image 1.17.0 and Pillow 10.2.0**: PDF-to-image conversion and handling.
- **asyncpg 0.29.0**: PostgreSQL client. Manages job metadata and results with full-text search.
- **google-cloud-pubsub 2.19.0**: Pub/Sub SDK. Decouples uploads from processing.
- **google-cloud-storage 2.14.0**: GCS SDK. Stores/retrieves blobs.
- **redis 5.0.1**: Redis client. Caches search results.
- **python-dotenv 1.0.0 and asyncio**: Env loading and concurrency.

### Hardware/Infrastructure Components
- **Cloud Run**: Serverless compute for API and jobs (auto-scales 0-1000, 1Gi/2 CPU).
- **Cloud SQL (PostgreSQL 15 on db-f1-micro VM)**: Relational DB for jobs/results.
- **Memorystore (Redis 7, Basic tier, 1GB RAM)**: In-memory cache.
- **Cloud Storage (Standard buckets)**: Object storage for documents.
- **Cloud Pub/Sub (standard tier)**: Messaging queue.
- **VPC Connector**: Private networking for SQL/Redis.
- **Local Laptop (Intel i7, 16GB RAM)**: Development/testing.

## Features
- ✅ Upload PNG/PDF for OCR processing
- ✅ Asynchronous job tracking
- ✅ Full-text search across results
- ✅ Redis caching for fast queries
- ✅ Auto-scaling with Cloud Run
- ✅ Monitoring and logging via gcloud
- ✅ REST API with OpenAPI docs

## 📋 Prerequisites
- GCP account with billing enabled
- gcloud CLI configured (`gcloud auth login`)
- Docker for local testing (optional)
- Python 3.11+ for load testing

## 🚀 Quick Start: Deploy to GCP
1. **Set Project/Region**:
   ```bash
   export GCP_PROJECT_ID=<your-project-id>
   export GCP_REGION=us-central1
   gcloud config set project $GCP_PROJECT_ID
   ```

2. **Deploy Infrastructure**:
   ```bash
   cd infrastructure
   ./deploy.sh  # Creates buckets, Pub/Sub, SQL, Redis, VPC, API
   ```

3. **Get API URL**:
   ```bash
   API_URL=$(gcloud run services describe docuscan-api --region=$GCP_REGION --format='value(status.url)')
   echo $API_URL
   ```

4. **Initialize DB Schema**:
   ```bash
   curl -X POST -H "Content-Length: 0" "$API_URL/admin/init-db"
   ```

5. **Test Upload and Processing**:
   ```bash
   # Generate test PNG (run once)
   python generate_test_pngs.py
   
   # Upload
   curl -X POST -F 'file=@test_pngs/test1.png' "$API_URL/upload"  # Returns {"job_id":"<your-job-id>"}
   
   # Exec worker
   gcloud run jobs execute docuscan-worker --region=$GCP_REGION
   
   # Set JOB_ID from upload
   JOB_ID="<your-job-id>"
   
   # Poll status
   curl "$API_URL/jobs/$JOB_ID"  # {"status":"completed"}
   
   # Get results
   curl "$API_URL/jobs/$JOB_ID/results"  # {"extracted_text":"Test OCR: Invoice Total $10",...}
   ```

6. **Test Search**:
   ```bash
   curl -X POST "$API_URL/search" -H "Content-Type: application/json" -d '{"query":"invoice total","limit":1}'
   ```

## Load Testing with Locust
Test capacity with concurrent uploads (e.g., 20 users, ~40 requests in 2 min, 7 RPS, 0 fails).

1. **Install in Venv** (one-time):
   ```powershell
   # In PowerShell
   python -m venv locust-env
   locust-env\Scripts\Activate.ps1
   pip install locust
   deactivate
   ```

2. **Run Burst**:
   ```powershell
   locust-env\Scripts\Activate.ps1
   locust -f load_test.py --headless -u 20 -r 10 -t 2m --csv=docuscan-burst --host=$API_URL
   deactivate
   ```
   - Outputs CSVs (e.g., `docuscan-burst_stats_history.csv`) for Excel plots (RPS vs. time, latency stability).

## 🧪 API Documentation
### Upload Document
```bash
POST /upload
curl -X POST -F 'file=@test.png' "$API_URL/upload"
```
Response:
```json
{"job_id":"uuid","status":"queued","message":"Document uploaded and queued"}
```

### Check Job Status
```bash
GET /jobs/{job_id}
curl "$API_URL/jobs/$JOB_ID"
```
Response:
```json
{"job_id":"uuid","status":"completed","file_name":"test.png"}
```

### Get Results
```bash
GET /jobs/{job_id}/results
curl "$API_URL/jobs/$JOB_ID/results"
```
Response:
```json
{"job_id":"uuid","extracted_text":"Test OCR: Invoice Total $10","confidence":0.95}
```

### Search Documents
```bash
POST /search
curl -X POST "$API_URL/search" -H "Content-Type: application/json" -d '{"query":"invoice total","limit":1}'
```
Response:
```json
{"query":"invoice total","total_results":1,"results":[{"job_id":"uuid","matched_text":"Invoice Total $10","relevance_score":0.85}]}
```

## 🐛 Troubleshooting
### Worker not processing
```bash
gcloud run jobs executions logs <exec-id> --region=us-central1 --limit=50
gcloud pubsub subscriptions pull ocr-jobs-sub --limit=1 --auto-ack
```

### Database issues
```bash
gcloud sql connect docuscan-db --user=postgres
# In psql: \c docuscan; \dt; \q
```

### Storage access
```bash
gsutil ls gs://docuscan-uploads-$GCP_PROJECT_ID/
```

## 🧹 Cleanup (Avoid Charges)
```bash
cd infrastructure
./cleanup.sh  # Deletes all resources
```

## 📊 Performance
- API: <500ms uncached
- OCR: 1-3s per small image
- Throughput: 50-100 jobs/min
- Cache Hit: 85%+

## 📁 Project Structure
```
docuscan/
├── api/                    # FastAPI app
│   └── services/           # Services (storage, database, etc.)
├── worker/                 # OCR worker
├── infrastructure/         # Deployment
├── test_pngs/              # Test files
├── load_test.py            # Load testing
├── cloudbuild-*.yaml       # Builds
├── generate_test_pngs.py   # PNG generator
└── deploy.sh               # GCP deploy
```

## 🔒 Security
- VPC for private access
- Env vars for secrets
- Add auth for production

## 🤝 Contributing
Fork, branch, test, PR.

## 📝 License
Educational use only. CU Boulder, Fall 2025.

## 👥 Team
- Saahil Jawale
- William Hinkley

## 📚 References
- GCP Run Docs: cloud.google.com/run
- Tesseract: github.com/tesseract-ocr
- FastAPI: fastapi.tiangolo.com