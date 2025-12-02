"""
DocuScan API - Cloud-Based OCR Service
FastAPI backend for document upload, processing, and search
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DocuScan API",
    description="Cloud-based OCR service for document processing",
    version="1.0.0"
)

# Import services (these will be implemented separately)
from api.services.storage import StorageService
from api.services.database import DatabaseService
from api.services.cache import CacheService
from api.services.pubsub import PubSubService

# Initialize services
storage_service = StorageService()
db_service = DatabaseService()
cache_service = CacheService()
pubsub_service = PubSubService()

# Pydantic models
class JobStatus(BaseModel):
    job_id: str
    status: str  # queued, processing, completed, failed
    created_at: datetime
    updated_at: datetime
    file_name: str
    file_type: str

class JobResult(BaseModel):
    job_id: str
    extracted_text: str
    page_count: int
    confidence: Optional[float]

class SearchRequest(BaseModel):
    query: str
    limit: int = 10

class SearchResult(BaseModel):
    job_id: str
    file_name: str
    matched_text: str
    relevance_score: float

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run monitoring"""
    return {
        "status": "healthy",
        "service": "DocuScan API",
        "timestamp": datetime.utcnow().isoformat()
    }

# Document upload endpoint
@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document (PDF or image) for OCR processing
    
    Returns:
        job_id: Unique identifier for tracking the processing job
    """
    try:
        # Validate file type
        allowed_types = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {allowed_types}"
            )
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Read file content
        file_content = await file.read()
        
        # Upload to Cloud Storage
        storage_path = await storage_service.upload_file(
            job_id=job_id,
            file_name=file.filename,
            file_content=file_content,
            content_type=file.content_type
        )
        
        # Create job record in database
        await db_service.create_job(
            job_id=job_id,
            file_name=file.filename,
            file_type=file.content_type,
            storage_path=storage_path,
            status='queued'
        )
        
        # Cache initial job status
        await cache_service.set_job_status(job_id, 'queued')
        
        # Publish message to Pub/Sub
        await pubsub_service.publish_job(
            job_id=job_id,
            storage_path=storage_path,
            file_type=file.content_type
        )
        
        logger.info(f"Document uploaded successfully: {job_id}")
        
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "status": "queued",
                "message": "Document uploaded and queued for processing"
            }
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get job status endpoint
@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a processing job
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Job status information
    """
    try:
        # Check cache first
        cached_status = await cache_service.get_job_status(job_id)
        
        if cached_status:
            logger.info(f"Cache hit for job: {job_id}")
            job_data = await db_service.get_job(job_id)
            return JobStatus(**job_data)
        
        # If not in cache, query database
        logger.info(f"Cache miss for job: {job_id}")
        job_data = await db_service.get_job(job_id)
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Update cache
        await cache_service.set_job_status(job_id, job_data['status'])
        
        return JobStatus(**job_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get job results endpoint
@app.get("/jobs/{job_id}/results")
async def get_job_results(job_id: str):
    """
    Get the OCR results for a completed job
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Extracted text and metadata
    """
    try:
        # Check if job is completed
        job_data = await db_service.get_job(job_id)
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job_data['status'] != 'completed':
            raise HTTPException(
                status_code=400,
                detail=f"Job is not completed. Current status: {job_data['status']}"
            )
        
        # Check cache for results
        cached_results = await cache_service.get_job_results(job_id)
        
        if cached_results:
            logger.info(f"Cache hit for results: {job_id}")
            return JobResult(**cached_results)
        
        # Get results from database
        results = await db_service.get_job_results(job_id)
        
        if not results:
            raise HTTPException(status_code=404, detail="Results not found")
        
        # Cache results
        await cache_service.set_job_results(job_id, results)
        
        return JobResult(**results)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Search endpoint
@app.post("/search")
async def search_documents(search_request: SearchRequest):
    """
    Search across all processed documents
    
    Args:
        search_request: Search query and parameters
        
    Returns:
        List of matching documents
    """
    try:
        results = await db_service.search_documents(
            query=search_request.query,
            limit=search_request.limit
        )
        
        search_results = [SearchResult(**result) for result in results]
        
        logger.info(f"Search completed: {len(results)} results found")
        
        return {
            "query": search_request.query,
            "total_results": len(results),
            "results": search_results
        }
        
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# List all jobs endpoint (for debugging)
@app.get("/jobs")
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, description="Maximum number of jobs to return")
):
    """
    List all processing jobs
    
    Args:
        status: Optional status filter
        limit: Maximum number of results
        
    Returns:
        List of jobs
    """
    try:
        jobs = await db_service.list_jobs(status=status, limit=limit)
        return {
            "total": len(jobs),
            "jobs": jobs
        }
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
