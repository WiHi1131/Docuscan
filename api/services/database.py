"""
Database Service - Cloud SQL PostgreSQL integration
Handles job metadata and OCR results storage
"""

import asyncpg
import os
from typing import Optional, List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DatabaseService:
    """Service for managing database operations with Cloud SQL"""
    
    def __init__(self):
        """Initialize database connection pool"""
        self.db_user = os.getenv('DB_USER', 'postgres')
        self.db_password = os.getenv('DB_PASSWORD', 'password')
        self.db_host = os.getenv('DB_HOST', 'localhost')
        self.db_port = os.getenv('DB_PORT', '5432')
        self.db_name = os.getenv('DB_NAME', 'docuscan')
        
        self.pool = None
    
    async def _get_pool(self):
        """Get or create connection pool"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                user=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                min_size=1,
                max_size=10
            )
            logger.info("Database connection pool created")
        return self.pool
    
    async def initialize_schema(self):
        """Create database tables if they don't exist"""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            # Create documents table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    job_id VARCHAR(36) PRIMARY KEY,
                    file_name VARCHAR(255) NOT NULL,
                    file_type VARCHAR(50) NOT NULL,
                    storage_path TEXT NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create OCR results table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS ocr_results (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(36) REFERENCES documents(job_id),
                    extracted_text TEXT,
                    page_count INTEGER,
                    confidence FLOAT,
                    processing_time FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create full-text search index
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_ocr_text_search 
                ON ocr_results USING gin(to_tsvector('english', extracted_text))
            ''')
            
            logger.info("Database schema initialized")
    
    async def create_job(
        self,
        job_id: str,
        file_name: str,
        file_type: str,
        storage_path: str,
        status: str = 'queued'
    ) -> Dict:
        """Create a new job record"""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO documents (job_id, file_name, file_type, storage_path, status)
                VALUES ($1, $2, $3, $4, $5)
            ''', job_id, file_name, file_type, storage_path, status)
            
            logger.info(f"Job created: {job_id}")
            
            return {
                'job_id': job_id,
                'file_name': file_name,
                'file_type': file_type,
                'status': status,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
    
    async def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job information by ID"""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT job_id, file_name, file_type, storage_path, status, 
                       created_at, updated_at
                FROM documents
                WHERE job_id = $1
            ''', job_id)
            
            if row:
                return dict(row)
            return None
    
    async def update_job_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None
    ):
        """Update job status"""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
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
        confidence: Optional[float] = None,
        processing_time: Optional[float] = None
    ):
        """Save OCR results"""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO ocr_results 
                (job_id, extracted_text, page_count, confidence, processing_time)
                VALUES ($1, $2, $3, $4, $5)
            ''', job_id, extracted_text, page_count, confidence, processing_time)
            
            # Update job status to completed
            await self.update_job_status(job_id, 'completed')
            
            logger.info(f"OCR results saved: {job_id}")
    
    async def get_job_results(self, job_id: str) -> Optional[Dict]:
        """Get OCR results for a job"""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT job_id, extracted_text, page_count, confidence
                FROM ocr_results
                WHERE job_id = $1
            ''', job_id)
            
            if row:
                return dict(row)
            return None
    
    async def search_documents(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict]:
        """Search documents using full-text search"""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT 
                    d.job_id,
                    d.file_name,
                    ts_headline('english', o.extracted_text, 
                                plainto_tsquery('english', $1),
                                'MaxWords=50, MinWords=25') as matched_text,
                    ts_rank(to_tsvector('english', o.extracted_text),
                            plainto_tsquery('english', $1)) as relevance_score
                FROM documents d
                JOIN ocr_results o ON d.job_id = o.job_id
                WHERE to_tsvector('english', o.extracted_text) @@ 
                      plainto_tsquery('english', $1)
                ORDER BY relevance_score DESC
                LIMIT $2
            ''', query, limit)
            
            return [dict(row) for row in rows]
    
    async def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """List all jobs with optional status filter"""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch('''
                    SELECT job_id, file_name, status, created_at, updated_at
                    FROM documents
                    WHERE status = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                ''', status, limit)
            else:
                rows = await conn.fetch('''
                    SELECT job_id, file_name, status, created_at, updated_at
                    FROM documents
                    ORDER BY created_at DESC
                    LIMIT $1
                ''', limit)
            
            return [dict(row) for row in rows]
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
