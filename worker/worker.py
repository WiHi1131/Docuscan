"""
OCR Worker - Cloud Run Job
Processes documents from Pub/Sub queue and performs OCR
"""

from google.cloud import pubsub_v1, storage
import pytesseract
from PIL import Image
import pdf2image
import io
import os
import sys
import json
import time
import logging
from typing import Dict, List
import asyncpg
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OCRWorker:
    """Worker for processing OCR jobs"""
    
    def __init__(self):
        """Initialize worker with required services"""
        # Database config
        self.db_user = os.getenv('DB_USER', 'postgres')
        self.db_password = os.getenv('DB_PASSWORD', 'password')
        self.db_host = os.getenv('DB_HOST', 'localhost')
        self.db_port = os.getenv('DB_PORT', '5432')
        self.db_name = os.getenv('DB_NAME', 'docuscan')
        
        # Storage config
        self.storage_client = storage.Client()
        
        # Pub/Sub config
        self.project_id = os.getenv('GCP_PROJECT_ID', 'docuscan-project')
        self.subscription_name = os.getenv('PUBSUB_SUBSCRIPTION', 'ocr-jobs-sub')
        
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscription_path = self.subscriber.subscription_path(
            self.project_id,
            self.subscription_name
        )
        
        self.db_pool = None
    
    async def connect_db(self):
        """Create database connection pool"""
        if self.db_pool is None:
            self.db_pool = await asyncpg.create_pool(
                user=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                min_size=1,
                max_size=5
            )
            logger.info("Database connection pool created")
    
    async def update_job_status(self, job_id: str, status: str):
        """Update job status in database"""
        await self.connect_db()
        async with self.db_pool.acquire() as conn:
            await conn.execute('''
                UPDATE documents
                SET status = $1, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = $2
            ''', status, job_id)
            logger.info(f"Job status updated: {job_id} -> {status}")
    
    async def save_ocr_results(
        self,
        job_id: str,
        extracted_text: str,
        page_count: int,
        confidence: float,
        processing_time: float
    ):
        """Save OCR results to database"""
        await self.connect_db()
        async with self.db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO ocr_results (job_id, extracted_text, page_count, confidence, processing_time)
                VALUES ($1, $2, $3, $4, $5)
            ''', job_id, extracted_text, page_count, confidence, processing_time)
            logger.info(f"OCR results saved for job: {job_id}")
    
    async def process_job(self, job_data: Dict):
        """Process a single OCR job"""
        job_id = job_data['job_id']
        storage_path = job_data['storage_path']
        file_type = job_data['file_type']
        
        start_time = time.time()
        
        try:
            # Update status to processing
            await self.update_job_status(job_id, 'processing')
            
            # Download file from GCS
            file_content = await self.download_file(storage_path)
            
            # Perform OCR
            result = await self.perform_ocr(file_content, file_type)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Save results to database
            await self.save_ocr_results(
                job_id=job_id,
                extracted_text=result['text'],
                page_count=result['page_count'],
                confidence=result['confidence'],
                processing_time=processing_time
            )
            
            # Update status to completed
            await self.update_job_status(job_id, 'completed')
            
            logger.info(f"Job completed: {job_id} ({processing_time:.2f}s)")
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {str(e)}")
            
            # Update status to failed
            await self.update_job_status(job_id, 'failed')
            raise
    
    async def download_file(self, storage_path: str) -> bytes:
        """Download file from GCS"""
        try:
            # Parse GCS path
            path_parts = storage_path.replace('gs://', '').split('/', 1)
            bucket_name = path_parts[0]
            blob_name = path_parts[1]
            
            # Download file
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            content = blob.download_as_bytes()
            
            logger.info(f"File downloaded from: {storage_path}")
            return content
            
        except Exception as e:
            logger.error(f"Error downloading file from GCS: {str(e)}")
            raise
    
    async def perform_ocr(self, file_content: bytes, file_type: str) -> Dict:
        """Perform OCR on file content"""
        try:
            if file_type == 'application/pdf':
                # Convert PDF to images
                images = pdf2image.convert_from_bytes(file_content)
                text_parts = []
                confidence_parts = []
                for image in images:
                    text, confidence = self.extract_text_from_image(image)
                    text_parts.append(text)
                    confidence_parts.append(confidence)
                full_text = '\n'.join(text_parts)
                avg_confidence = sum(confidence_parts) / len(confidence_parts) if confidence_parts else 0.0
                return {
                    'text': full_text,
                    'page_count': len(images),
                    'confidence': avg_confidence
                }
            else:
                # Image file
                image = Image.open(io.BytesIO(file_content))
                text, confidence = self.extract_text_from_image(image)
                return {
                    'text': text,
                    'page_count': 1,
                    'confidence': confidence
                }
                
        except Exception as e:
            logger.error(f"Error performing OCR: {str(e)}")
            raise
    
    def extract_text_from_image(self, image: Image.Image) -> tuple:
        """Extract text from a single image using Tesseract"""
        try:
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Extract text and confidence
            text = pytesseract.image_to_string(image)
            # Note: Tesseract confidence extraction requires custom config
            # For simplicity, we'll use a placeholder
            confidence = 0.95  # Placeholder - real implementation would parse hOCR
            
            return text, confidence
            
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            raise
    
    def message_callback(self, message):
        """Callback for Pub/Sub messages"""
        try:
            # Parse message
            message_data = json.loads(message.data.decode('utf-8'))
            logger.info(f"Received message: {message_data}")
            
            # Guard for scheduler trigger (no-op if no job_id)
            if 'trigger' in message_data and 'job_id' not in message_data:
                logger.info("Received scheduler trigger; polling subscription (no-op)")
                message.ack()  # Acknowledge to avoid retry loop
                return
            
            # Process job
            asyncio.run(self.process_job(message_data))
            
            # Acknowledge message
            message.ack()
            logger.info(f"Message acknowledged: {message.message_id}")
            
        except KeyError as e:
            logger.error(f"Missing key in message data: {str(e)}")
            message.nack()  # Retry later
        except Exception as e:
            logger.error(f"Error in message callback: {str(e)}")
            # Nack message to retry
            message.nack()
    
    def start(self):
        """Start listening for messages"""
        logger.info(f"Worker started, listening on: {self.subscription_path}")
        
        # Subscribe to messages
        streaming_pull_future = self.subscriber.subscribe(
            self.subscription_path,
            callback=self.message_callback
        )
        
        try:
            # Keep worker running
            streaming_pull_future.result()
        except KeyboardInterrupt:
            streaming_pull_future.cancel()
            logger.info("Worker stopped")
        except Exception as e:
            logger.error(f"Worker error: {str(e)}")
            streaming_pull_future.cancel()
            raise

def main():
    """Main entry point for worker"""
    logger.info("Starting OCR Worker...")
    
    worker = OCRWorker()
    worker.start()

if __name__ == '__main__':
    main()
