"""
Cache Service - Redis/Memorystore integration
Handles caching of job status and results
"""

import redis.asyncio as redis
import json
import os
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class CacheService:
    """Service for managing Redis cache operations"""
    
    def __init__(self):
        """Initialize Redis client"""
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))
        self.redis_password = os.getenv('REDIS_PASSWORD', None)
        
        # TTL for cache entries (in seconds)
        self.status_ttl = 300  # 5 minutes
        self.results_ttl = 3600  # 1 hour
        
        self.client = None
    
    async def _get_client(self):
        """Get or create Redis client"""
        if self.client is None:
            self.client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                decode_responses=True,
                encoding='utf-8'
            )
            logger.info("Redis client created")
        return self.client
    
    def _status_key(self, job_id: str) -> str:
        """Generate cache key for job status"""
        return f"job:status:{job_id}"
    
    def _results_key(self, job_id: str) -> str:
        """Generate cache key for job results"""
        return f"job:results:{job_id}"
    
    async def set_job_status(self, job_id: str, status: str):
        """
        Cache job status
        
        Args:
            job_id: Unique job identifier
            status: Job status (queued, processing, completed, failed)
        """
        try:
            client = await self._get_client()
            key = self._status_key(job_id)
            
            await client.setex(
                key,
                self.status_ttl,
                status
            )
            
            logger.info(f"Cached job status: {job_id} -> {status}")
            
        except Exception as e:
            logger.error(f"Error caching job status: {str(e)}")
            # Don't raise - cache failures shouldn't break the app
    
    async def get_job_status(self, job_id: str) -> Optional[str]:
        """
        Get cached job status
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            Job status if cached, None otherwise
        """
        try:
            client = await self._get_client()
            key = self._status_key(job_id)
            
            status = await client.get(key)
            
            if status:
                logger.info(f"Cache hit for job status: {job_id}")
            else:
                logger.info(f"Cache miss for job status: {job_id}")
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting cached job status: {str(e)}")
            return None
    
    async def set_job_results(self, job_id: str, results: Dict):
        """
        Cache job results
        
        Args:
            job_id: Unique job identifier
            results: OCR results dictionary
        """
        try:
            client = await self._get_client()
            key = self._results_key(job_id)
            
            # Serialize results to JSON
            results_json = json.dumps(results)
            
            await client.setex(
                key,
                self.results_ttl,
                results_json
            )
            
            logger.info(f"Cached job results: {job_id}")
            
        except Exception as e:
            logger.error(f"Error caching job results: {str(e)}")
    
    async def get_job_results(self, job_id: str) -> Optional[Dict]:
        """
        Get cached job results
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            OCR results if cached, None otherwise
        """
        try:
            client = await self._get_client()
            key = self._results_key(job_id)
            
            results_json = await client.get(key)
            
            if results_json:
                logger.info(f"Cache hit for job results: {job_id}")
                return json.loads(results_json)
            else:
                logger.info(f"Cache miss for job results: {job_id}")
                return None
            
        except Exception as e:
            logger.error(f"Error getting cached job results: {str(e)}")
            return None
    
    async def invalidate_job(self, job_id: str):
        """
        Invalidate all cache entries for a job
        
        Args:
            job_id: Unique job identifier
        """
        try:
            client = await self._get_client()
            
            status_key = self._status_key(job_id)
            results_key = self._results_key(job_id)
            
            await client.delete(status_key, results_key)
            
            logger.info(f"Cache invalidated for job: {job_id}")
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {str(e)}")
    
    async def get_cache_stats(self) -> Dict:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache stats
        """
        try:
            client = await self._get_client()
            info = await client.info('stats')
            
            return {
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'total_connections': info.get('total_connections_received', 0),
                'connected_clients': info.get('connected_clients', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {}
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")
