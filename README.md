# DocuScan - Cloud-Based OCR Service

A distributed, cloud-native document processing service that performs optical character recognition (OCR) on uploaded documents and makes the extracted text searchable.

## 🏗️ Architecture

DocuScan is built using a microservices architecture with the following components:

```
User → API (Cloud Run) → Pub/Sub → Worker (Cloud Run Jobs) → Results
         ↓                                    ↓
    Cloud Storage                        Cloud SQL
         ↓                                    ↓
    Redis Cache ←─────────────────────────────┘
```

### Components

1. **API Service** (FastAPI on Cloud Run)
   - REST API for document upload, status checking, and search
   - Validates uploads and queues jobs
   - Implements caching for improved performance

2. **Worker Service** (Python on Cloud Run Jobs)
   - Processes documents asynchronously
   - Uses Tesseract OCR for text extraction
   - Handles PDFs and images

3. **Cloud Storage** (Google Cloud Storage)
   - Stores uploaded documents and results
   - Two buckets: uploads and results

4. **Job Queue** (Google Cloud Pub/Sub)
   - Distributes OCR tasks to workers
   - Enables asynchronous processing

5. **Database** (Cloud SQL - PostgreSQL)
   - Stores job metadata and extracted text
   - Full-text search capabilities

6. **Cache** (Memorystore - Redis)
   - Caches job status and results
   - Reduces database load

## 🚀 Features

- ✅ Upload PDFs and images (PNG, JPEG) for OCR processing
- ✅ Asynchronous job processing with status tracking
- ✅ Full-text search across all processed documents
- ✅ Redis caching for improved response times
- ✅ Automatic scaling with Cloud Run
- ✅ Comprehensive monitoring and logging
- ✅ RESTful API with OpenAPI documentation

## 📋 Prerequisites

- Google Cloud Platform account
- Docker installed locally
- Python 3.11+
- `gcloud` CLI configured
- (Optional) Terraform for infrastructure as code

## 🛠️ Installation & Setup

### Option 1: Local Development with Docker Compose

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd docuscan
   ```

2. **Start services**
   ```bash
   docker-compose up -d
   ```

3. **Initialize database**
   ```bash
   curl -X POST http://localhost:8080/admin/init-db
   ```

4. **Test the API**
   ```bash
   curl http://localhost:8080/health
   ```

### Option 2: Deploy to Google Cloud

1. **Set your project ID**
   ```bash
   export GCP_PROJECT_ID=your-project-id
   export GCP_REGION=us-central1
   ```

2. **Run deployment script**
   ```bash
   cd infrastructure
   ./deploy.sh
   ```

3. **Or use Terraform**
   ```bash
   cd infrastructure/terraform
   terraform init
   terraform plan -var="project_id=$GCP_PROJECT_ID" -var="db_password=SecurePassword123"
   terraform apply
   ```

## 📖 API Documentation

### Upload Document
```bash
POST /upload
Content-Type: multipart/form-data

curl -X POST -F 'file=@document.pdf' http://localhost:8080/upload
```

Response:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "queued",
  "message": "Document uploaded and queued for processing"
}
```

### Check Job Status
```bash
GET /jobs/{job_id}

curl http://localhost:8080/jobs/123e4567-e89b-12d3-a456-426614174000
```

Response:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "file_name": "document.pdf",
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:31:30"
}
```

### Get Results
```bash
GET /jobs/{job_id}/results

curl http://localhost:8080/jobs/123e4567-e89b-12d3-a456-426614174000/results
```

Response:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "extracted_text": "This is the extracted text from your document...",
  "page_count": 5,
  "confidence": 92.5
}
```

### Search Documents
```bash
POST /search
Content-Type: application/json

curl -X POST http://localhost:8080/search \
  -H "Content-Type: application/json" \
  -d '{"query": "invoice", "limit": 10}'
```

Response:
```json
{
  "query": "invoice",
  "total_results": 3,
  "results": [
    {
      "job_id": "123e4567-e89b-12d3-a456-426614174000",
      "file_name": "invoice_2024.pdf",
      "matched_text": "...invoice number INV-2024-001...",
      "relevance_score": 0.95
    }
  ]
}
```

### List All Jobs
```bash
GET /jobs?status=completed&limit=50

curl http://localhost:8080/jobs?status=completed&limit=50
```

### Health Check
```bash
GET /health

curl http://localhost:8080/health
```

## 🧪 Testing

### Run Unit Tests
```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

### Test with Sample Files
```bash
# Upload a PDF
curl -X POST -F 'file=@sample.pdf' http://localhost:8080/upload

# Upload an image
curl -X POST -F 'file=@scan.jpg' http://localhost:8080/upload
```

## 📊 Monitoring

### View Logs (Local)
```bash
docker-compose logs -f api
docker-compose logs -f worker
```

### View Logs (Cloud)
```bash
gcloud logging read "resource.type=cloud_run_revision" --limit 50
```

### Check Cache Statistics
```bash
redis-cli INFO stats
```

### Database Monitoring
```bash
# Connect to database
gcloud sql connect docuscan-db --user=postgres

# View job statistics
SELECT status, COUNT(*) FROM documents GROUP BY status;
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Google Cloud Project ID | - |
| `DB_HOST` | PostgreSQL host | localhost |
| `DB_PORT` | PostgreSQL port | 5432 |
| `DB_NAME` | Database name | docuscan |
| `DB_USER` | Database user | postgres |
| `DB_PASSWORD` | Database password | - |
| `REDIS_HOST` | Redis host | localhost |
| `REDIS_PORT` | Redis port | 6379 |
| `GCS_UPLOAD_BUCKET` | Upload bucket name | docuscan-uploads |
| `GCS_RESULTS_BUCKET` | Results bucket name | docuscan-results |
| `PUBSUB_TOPIC` | Pub/Sub topic name | ocr-jobs |
| `PUBSUB_SUBSCRIPTION` | Subscription name | ocr-jobs-sub |

## 🎯 Performance

- **API Response Time**: < 100ms (cached), < 500ms (uncached)
- **OCR Processing Time**: 2-5 seconds per page
- **Throughput**: 100+ documents per minute with auto-scaling
- **Cache Hit Rate**: 85%+ for repeated queries

## 🏗️ Project Structure

```
docuscan/
├── api/                    # FastAPI application
│   ├── main.py            # API endpoints
│   └── services/          # Service implementations
│       ├── storage.py     # GCS integration
│       ├── database.py    # PostgreSQL operations
│       ├── cache.py       # Redis caching
│       └── pubsub.py      # Pub/Sub messaging
├── worker/                # OCR worker
│   └── worker.py          # Job processor
├── infrastructure/        # Deployment scripts
│   ├── deploy.sh          # GCP deployment script
│   └── terraform/         # Terraform configs
├── tests/                 # Test suite
│   └── test_api.py        # API tests
├── docker-compose.yml     # Local development
├── Dockerfile.api         # API container
├── Dockerfile.worker      # Worker container
├── requirements.txt       # API dependencies
└── requirements-worker.txt # Worker dependencies
```

## 🔒 Security Considerations

- Use secret manager for sensitive credentials
- Enable VPC for private networking
- Use Cloud Armor for DDoS protection
- Implement authentication (not included in demo)
- Regular security updates for dependencies
- Enable audit logging

## 📈 Scaling

- **API**: Automatically scales 0-10 instances based on traffic
- **Workers**: Configurable concurrency and task timeout
- **Database**: Upgrade tier as needed (db-f1-micro → db-n1-standard-1)
- **Cache**: Upgrade to standard tier for high availability

## 🐛 Troubleshooting

### Worker not processing jobs
```bash
# Check Pub/Sub subscription
gcloud pubsub subscriptions describe ocr-jobs-sub

# Check worker logs
gcloud logging read "resource.type=cloud_run_job" --limit 50
```

### Database connection issues
```bash
# Verify Cloud SQL instance
gcloud sql instances describe docuscan-db

# Check connection from API
gcloud run services describe docuscan-api --format="value(spec.template.metadata.annotations)"
```

### Storage access errors
```bash
# Check bucket permissions
gsutil iam get gs://docuscan-uploads-$PROJECT_ID
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## 👥 Team

- Saahil Jawale
- William Hinkley

## 📚 References

- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Cloud SQL Best Practices](https://cloud.google.com/sql/docs/postgres/best-practices)

## 🎓 Educational Value

This project demonstrates:
- Microservices architecture
- Asynchronous job processing
- Cloud-native design patterns
- Caching strategies
- Full-text search implementation
- Container orchestration
- Infrastructure as code
- API design best practices

---

**Note**: This is an educational project. For production use, implement proper authentication, rate limiting, and enhanced security measures.
