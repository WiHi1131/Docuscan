"""
Test Suite for DocuScan API
Run with: pytest tests/test_api.py
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app
import io

client = TestClient(app)

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "DocuScan API"

def test_upload_pdf():
    """Test PDF upload"""
    # Create a simple test PDF (in real scenario, use actual PDF)
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
    
    files = {
        "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    response = client.post("/upload", files=files)
    assert response.status_code == 202
    assert "job_id" in response.json()
    assert response.json()["status"] == "queued"

def test_upload_image():
    """Test image upload"""
    # Create a minimal PNG (1x1 pixel)
    png_content = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
        b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
        b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    
    files = {
        "file": ("test.png", io.BytesIO(png_content), "image/png")
    }
    
    response = client.post("/upload", files=files)
    assert response.status_code == 202
    assert "job_id" in response.json()

def test_upload_invalid_type():
    """Test uploading invalid file type"""
    txt_content = b"This is a text file"
    
    files = {
        "file": ("test.txt", io.BytesIO(txt_content), "text/plain")
    }
    
    response = client.post("/upload", files=files)
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]

def test_get_job_status_not_found():
    """Test getting status of non-existent job"""
    fake_job_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/jobs/{fake_job_id}")
    assert response.status_code == 404

def test_get_job_results_not_completed():
    """Test getting results of non-completed job"""
    # First upload a file to get a job_id
    pdf_content = b"%PDF-1.4\n%%EOF"
    files = {
        "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    upload_response = client.post("/upload", files=files)
    job_id = upload_response.json()["job_id"]
    
    # Try to get results immediately (should not be completed yet)
    response = client.get(f"/jobs/{job_id}/results")
    assert response.status_code == 400
    assert "not completed" in response.json()["detail"]

def test_search_endpoint():
    """Test search functionality"""
    search_request = {
        "query": "test",
        "limit": 10
    }
    
    response = client.post("/search", json=search_request)
    assert response.status_code == 200
    assert "results" in response.json()
    assert "total_results" in response.json()

def test_list_jobs():
    """Test listing all jobs"""
    response = client.get("/jobs")
    assert response.status_code == 200
    assert "jobs" in response.json()
    assert "total" in response.json()

def test_list_jobs_with_filter():
    """Test listing jobs with status filter"""
    response = client.get("/jobs?status=completed&limit=10")
    assert response.status_code == 200
    assert "jobs" in response.json()

@pytest.mark.asyncio
async def test_concurrent_uploads():
    """Test multiple concurrent uploads"""
    import asyncio
    
    async def upload_file():
        pdf_content = b"%PDF-1.4\n%%EOF"
        files = {
            "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        return client.post("/upload", files=files)
    
    # Upload 5 files concurrently
    tasks = [upload_file() for _ in range(5)]
    responses = await asyncio.gather(*tasks)
    
    # All should succeed
    for response in responses:
        assert response.status_code == 202
        assert "job_id" in response.json()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
