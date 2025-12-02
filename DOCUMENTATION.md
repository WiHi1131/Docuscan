# DocuScan - Technical Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Details](#architecture-details)
3. [API Reference](#api-reference)
4. [Database Schema](#database-schema)
5. [Deployment Guide](#deployment-guide)
6. [Monitoring & Debugging](#monitoring--debugging)
7. [Performance Tuning](#performance-tuning)

## System Overview

DocuScan is a distributed cloud-based OCR (Optical Character Recognition) service that enables users to upload documents (PDFs and images), processes them asynchronously to extract text, and provides full-text search capabilities across all processed documents.

### Key Technologies
- **Backend**: FastAPI (Python 3.11)
- **OCR Engine**: Tesseract OCR
- **Cloud Platform**: Google Cloud Platform
- **Compute**: Cloud Run (API), Cloud Run Jobs (Workers)
- **Storage**: Cloud Storage (GCS)
- **Database**: Cloud SQL (PostgreSQL 15)
- **Cache**: Memorystore (Redis)
- **Messaging**: Cloud Pub/Sub

## Architecture Details

### Component Flow

1. **Document Upload Flow**
   ```
   Client → API Server → Validate File
                      → Upload to GCS
                      → Create DB Record (status: queued)
                      → Publish to Pub/Sub
                      → Cache Status
                      → Return Job ID
   ```

2. **Processing Flow**
   ```
   Pub/Sub Message → Worker Instance
                  → Update Status (processing)
                  → Download from GCS
                  → Run Tesseract OCR
                  → Extract Text
                  → Save to Database
                  → Update Status (completed)
                  → Cache Results
   ```

3. **Retrieval Flow**
   ```
   Client → API Server → Check Redis Cache
                      → [Cache Hit] Return Cached Data
                      → [Cache Miss] Query Database
                                  → Cache Results
                                  → Return Data
   ```

### Data Flow Diagram

```
┌─────────┐
│ Client  │
└────┬────┘
     │ 1. POST /upload
     ▼
┌─────────────────┐
│   API Server    │
│  (Cloud Run)    │
└────┬────┬───┬───┘
     │    │   │
     │    │   │ 3. Pub/Sub
     │    │   └──────────────┐
     │    │                  │
     │    │ 2. Store         ▼
     │    ▼              ┌──────────┐
     │ ┌─────┐          │  Pub/Sub │
     │ │ GCS │          │  Topic   │
     │ └─────┘          └────┬─────┘
     │                       │
     │ 4. Save Job           │ 5. Trigger
     ▼                       ▼
┌──────────┐         ┌──────────────┐
│Cloud SQL │         │    Worker    │
│PostgreSQL│◄────────│ (Cloud Run   │
└────┬─────┘         │    Jobs)     │
     │               └──────────────┘
     │ 6. Cache              │
     ▼                       │
┌─────────┐                 │
│  Redis  │◄────────────────┘
└─────────┘         7. Cache Results
```

## API Reference

### Authentication
Current version: No authentication (demo only)
Production: Implement API keys or OAuth2

### Endpoints

#### POST /upload
Upload a document for OCR processing.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: `file` (PDF or image)

**Supported File Types:**
- `application/pdf`
- `image/png`
- `image/jpeg`
- `image/jpg`

**Response (202 Accepted):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Document uploaded and queued for processing"
}
```

**Error Responses:**
- 400: Invalid file type
- 500: Server error

#### GET /jobs/{job_id}
Get the status of a processing job.

**Request:**
- Method: `GET`
- Path: `/jobs/{job_id}`

**Response (200 OK):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "file_name": "document.pdf",
  "file_type": "application/pdf",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:31:30Z"
}
```

**Status Values:**
- `queued`: Job is waiting to be processed
- `processing`: OCR is in progress
- `completed`: Processing finished successfully
- `failed`: Processing encountered an error

#### GET /jobs/{job_id}/results
Retrieve OCR results for a completed job.

**Request:**
- Method: `GET`
- Path: `/jobs/{job_id}/results`

**Response (200 OK):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "extracted_text": "Full extracted text from the document...",
  "page_count": 5,
  "confidence": 92.5
}
```

**Error Responses:**
- 404: Job not found
- 400: Job not completed yet

#### POST /search
Search across all processed documents.

**Request:**
- Method: `POST`
- Content-Type: `application/json`
- Body:
```json
{
  "query": "search terms",
  "limit": 10
}
```

**Response (200 OK):**
```json
{
  "query": "search terms",
  "total_results": 3,
  "results": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "file_name": "document.pdf",
      "matched_text": "...highlighted search terms...",
      "relevance_score": 0.95
    }
  ]
}
```

#### GET /jobs
List all jobs with optional filtering.

**Request:**
- Method: `GET`
- Query Parameters:
  - `status` (optional): Filter by status
  - `limit` (optional, default: 50): Maximum results

**Response (200 OK):**
```json
{
  "total": 25,
  "jobs": [...]
}
```

#### GET /health
Health check endpoint.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "DocuScan API",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Database Schema

### Table: documents

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| job_id | VARCHAR(36) | PRIMARY KEY | Unique job identifier (UUID) |
| file_name | VARCHAR(255) | NOT NULL | Original filename |
| file_type | VARCHAR(50) | NOT NULL | MIME type |
| storage_path | TEXT | NOT NULL | GCS path to file |
| status | VARCHAR(20) | NOT NULL | Current job status |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

**Indexes:**
- Primary key on `job_id`
- Index on `status` for filtering
- Index on `created_at` for sorting

### Table: ocr_results

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment ID |
| job_id | VARCHAR(36) | FOREIGN KEY | References documents(job_id) |
| extracted_text | TEXT | | Full extracted text |
| page_count | INTEGER | | Number of pages processed |
| confidence | FLOAT | | Average OCR confidence (0-100) |
| processing_time | FLOAT | | Time taken in seconds |
| created_at | TIMESTAMP | DEFAULT NOW() | Result timestamp |

**Indexes:**
- Primary key on `id`
- Foreign key on `job_id`
- Full-text search index on `extracted_text` (GIN index with tsvector)

### Full-Text Search Index

```sql
CREATE INDEX idx_ocr_text_search 
ON ocr_results USING gin(to_tsvector('english', extracted_text));
```

This enables efficient full-text search queries:
```sql
SELECT * FROM ocr_results 
WHERE to_tsvector('english', extracted_text) @@ plainto_tsquery('english', 'search term');
```

## Deployment Guide

### Prerequisites
- Google Cloud account with billing enabled
- `gcloud` CLI installed and configured
- Docker installed
- Project permissions: Owner or Editor

### Step-by-Step Deployment

#### 1. Set Environment Variables
```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
```

#### 2. Initialize GCP Project
```bash
gcloud config set project $GCP_PROJECT_ID
```

#### 3. Run Automated Deployment
```bash
cd infrastructure
./deploy.sh
```

#### 4. Manual Steps (if needed)

**Create Cloud SQL Instance:**
```bash
gcloud sql instances create docuscan-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$GCP_REGION
```

**Create Database:**
```bash
gcloud sql databases create docuscan --instance=docuscan-db
```

**Deploy API:**
```bash
gcloud run deploy docuscan-api \
  --image gcr.io/$GCP_PROJECT_ID/docuscan-api \
  --region $GCP_REGION \
  --allow-unauthenticated
```

**Deploy Worker:**
```bash
gcloud run jobs create docuscan-worker \
  --image gcr.io/$GCP_PROJECT_ID/docuscan-worker \
  --region $GCP_REGION
```

### Local Development Setup

```bash
# Clone repository
git clone <repo-url>
cd docuscan

# Set up environment
make setup

# Start services
make start

# View logs
make logs

# Run tests
make test
```

## Monitoring & Debugging

### Cloud Logging

**View API Logs:**
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=docuscan-api" \
  --limit 50 --format json
```

**View Worker Logs:**
```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=docuscan-worker" \
  --limit 50 --format json
```

### Metrics

**Key Metrics to Monitor:**
- API request latency (p50, p95, p99)
- Request rate (requests/second)
- Error rate (%)
- Worker processing time
- Cache hit rate
- Database connection pool usage
- Queue depth (Pub/Sub)

**View Metrics:**
```bash
gcloud monitoring dashboards create --config-from-file=monitoring-dashboard.json
```

### Common Issues

#### 1. Jobs Stuck in "Queued" Status
**Cause:** Worker not processing messages
**Solution:**
- Check worker logs
- Verify Pub/Sub subscription exists
- Check worker has correct permissions

#### 2. "Job Not Found" Errors
**Cause:** Database connection issue
**Solution:**
- Verify Cloud SQL instance is running
- Check connection string
- Verify network connectivity

#### 3. OCR Quality Issues
**Cause:** Poor image quality or unsupported format
**Solution:**
- Preprocess images (enhance contrast)
- Use higher resolution scans
- Check Tesseract language support

## Performance Tuning

### API Optimization

1. **Redis Caching**
   - Cache TTL: 5 minutes for status, 1 hour for results
   - Implement cache warming for frequently accessed jobs

2. **Database Connection Pooling**
   - Min connections: 1
   - Max connections: 10
   - Connection timeout: 30s

3. **Response Compression**
   - Enable gzip compression for large text responses

### Worker Optimization

1. **Batch Processing**
   - Process multiple pages in parallel
   - Use multiprocessing for CPU-intensive OCR

2. **Resource Allocation**
   - Memory: 1GB minimum (2GB for large PDFs)
   - CPU: 2 cores
   - Timeout: 10 minutes

3. **Image Preprocessing**
   - Convert to grayscale
   - Enhance contrast
   - Remove noise

### Database Optimization

1. **Indexing**
   - Maintain indexes on frequently queried columns
   - Use partial indexes for status filtering

2. **Query Optimization**
   - Use EXPLAIN ANALYZE for slow queries
   - Implement pagination for large result sets

3. **Connection Management**
   - Use connection pooling
   - Set appropriate idle timeout

### Cost Optimization

1. **Cloud Run**
   - Set minimum instances to 0 for cost savings
   - Use request-based pricing

2. **Cloud Storage**
   - Implement lifecycle policies
   - Delete processed documents after 30 days

3. **Cloud SQL**
   - Start with db-f1-micro
   - Upgrade only when needed
   - Enable automatic backup deletion

---

*For questions or issues, please refer to the GitHub repository or contact the development team.*
