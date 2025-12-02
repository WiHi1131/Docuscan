"""
Storage Service - Google Cloud Storage integration
Handles document upload and retrieval
"""

from google.cloud import storage
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class StorageService:
    """Service for managing document storage in Google Cloud Storage"""
    
    def __init__(self):
        """Initialize GCS client and bucket"""
        self.client = storage.Client()
        self.upload_bucket_name = os.getenv('GCS_UPLOAD_BUCKET', 'docuscan-uploads')
        self.results_bucket_name = os.getenv('GCS_RESULTS_BUCKET', 'docuscan-results')
        
        # Get or create buckets
        self.upload_bucket = self._get_or_create_bucket(self.upload_bucket_name)
        self.results_bucket = self._get_or_create_bucket(self.results_bucket_name)
    
    def _get_or_create_bucket(self, bucket_name: str):
        """Get existing bucket or create new one"""
        try:
            bucket = self.client.bucket(bucket_name)
            if not bucket.exists():
                bucket = self.client.create_bucket(bucket_name)
                logger.info(f"Created bucket: {bucket_name}")
            return bucket
        except Exception as e:
            logger.error(f"Error accessing bucket {bucket_name}: {str(e)}")
            raise
    
    async def upload_file(
        self,
        job_id: str,
        file_name: str,
        file_content: bytes,
        content_type: str
    ) -> str:
        """
        Upload file to GCS
        
        Args:
            job_id: Unique job identifier
            file_name: Original file name
            file_content: File content as bytes
            content_type: MIME type of the file
            
        Returns:
            GCS path to the uploaded file
        """
        try:
            # Create blob path
            blob_name = f"{job_id}/{file_name}"
            blob = self.upload_bucket.blob(blob_name)
            
            # Upload file
            blob.upload_from_string(file_content, content_type=content_type)
            
            # Make blob publicly readable (optional, for testing)
            # blob.make_public()
            
            storage_path = f"gs://{self.upload_bucket_name}/{blob_name}"
            logger.info(f"File uploaded to: {storage_path}")
            
            return storage_path
            
        except Exception as e:
            logger.error(f"Error uploading file to GCS: {str(e)}")
            raise
    
    async def download_file(self, storage_path: str) -> bytes:
        """
        Download file from GCS
        
        Args:
            storage_path: GCS path (gs://bucket/path)
            
        Returns:
            File content as bytes
        """
        try:
            # Parse GCS path
            path_parts = storage_path.replace('gs://', '').split('/', 1)
            bucket_name = path_parts[0]
            blob_name = path_parts[1]
            
            # Download file
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            content = blob.download_as_bytes()
            
            logger.info(f"File downloaded from: {storage_path}")
            return content
            
        except Exception as e:
            logger.error(f"Error downloading file from GCS: {str(e)}")
            raise
    
    async def upload_results(
        self,
        job_id: str,
        results_content: str
    ) -> str:
        """
        Upload OCR results to GCS
        
        Args:
            job_id: Unique job identifier
            results_content: Extracted text
            
        Returns:
            GCS path to the results file
        """
        try:
            blob_name = f"{job_id}/results.txt"
            blob = self.results_bucket.blob(blob_name)
            
            # Upload results as text
            blob.upload_from_string(results_content, content_type='text/plain')
            
            storage_path = f"gs://{self.results_bucket_name}/{blob_name}"
            logger.info(f"Results uploaded to: {storage_path}")
            
            return storage_path
            
        except Exception as e:
            logger.error(f"Error uploading results to GCS: {str(e)}")
            raise
    
    async def delete_file(self, storage_path: str) -> bool:
        """
        Delete file from GCS
        
        Args:
            storage_path: GCS path (gs://bucket/path)
            
        Returns:
            True if successful
        """
        try:
            # Parse GCS path
            path_parts = storage_path.replace('gs://', '').split('/', 1)
            bucket_name = path_parts[0]
            blob_name = path_parts[1]
            
            # Delete file
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.delete()
            
            logger.info(f"File deleted: {storage_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file from GCS: {str(e)}")
            return False
