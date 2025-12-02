"""
Pub/Sub Service - Google Cloud Pub/Sub integration
Handles job queue and worker communication
"""

from google.cloud import pubsub_v1
import json
import os
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class PubSubService:
    """Service for managing Pub/Sub messaging"""
    
    def __init__(self):
        """Initialize Pub/Sub publisher and subscriber"""
        self.project_id = os.getenv('GCP_PROJECT_ID', 'docuscan-project')
        self.topic_name = os.getenv('PUBSUB_TOPIC', 'ocr-jobs')
        
        # Initialize publisher
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)
        
        # Create topic if it doesn't exist
        self._create_topic_if_not_exists()
    
    def _create_topic_if_not_exists(self):
        """Create Pub/Sub topic if it doesn't exist"""
        try:
            self.publisher.get_topic(request={"topic": self.topic_path})
            logger.info(f"Topic exists: {self.topic_path}")
        except Exception:
            try:
                self.publisher.create_topic(request={"name": self.topic_path})
                logger.info(f"Topic created: {self.topic_path}")
            except Exception as e:
                logger.error(f"Error creating topic: {str(e)}")
    
    async def publish_job(
        self,
        job_id: str,
        storage_path: str,
        file_type: str
    ) -> str:
        """
        Publish a job message to Pub/Sub
        
        Args:
            job_id: Unique job identifier
            storage_path: GCS path to the uploaded file
            file_type: MIME type of the file
            
        Returns:
            Message ID
        """
        try:
            # Create message payload
            message_data = {
                'job_id': job_id,
                'storage_path': storage_path,
                'file_type': file_type
            }
            
            # Convert to JSON and encode
            message_json = json.dumps(message_data)
            message_bytes = message_json.encode('utf-8')
            
            # Publish message
            future = self.publisher.publish(
                self.topic_path,
                message_bytes,
                job_id=job_id  # Custom attribute
            )
            
            # Wait for publish to complete
            message_id = future.result()
            
            logger.info(f"Published job to Pub/Sub: {job_id} (message_id: {message_id})")
            
            return message_id
            
        except Exception as e:
            logger.error(f"Error publishing job to Pub/Sub: {str(e)}")
            raise
    
    def create_subscription(self, subscription_name: str) -> str:
        """
        Create a subscription to the OCR jobs topic
        
        Args:
            subscription_name: Name for the subscription
            
        Returns:
            Subscription path
        """
        try:
            subscriber = pubsub_v1.SubscriberClient()
            subscription_path = subscriber.subscription_path(
                self.project_id,
                subscription_name
            )
            
            # Check if subscription exists
            try:
                subscriber.get_subscription(request={"subscription": subscription_path})
                logger.info(f"Subscription exists: {subscription_path}")
            except Exception:
                # Create subscription with push config for Cloud Run Jobs
                request = {
                    "name": subscription_path,
                    "topic": self.topic_path,
                    "ack_deadline_seconds": 600,  # 10 minutes for OCR processing
                }
                subscriber.create_subscription(request=request)
                logger.info(f"Subscription created: {subscription_path}")
            
            return subscription_path
            
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            raise
    
    async def publish_result(
        self,
        job_id: str,
        status: str,
        results: Dict = None
    ):
        """
        Publish processing result (for monitoring/notifications)
        
        Args:
            job_id: Unique job identifier
            status: Processing status
            results: Optional results data
        """
        try:
            # Create results topic if needed
            results_topic_name = f"{self.topic_name}-results"
            results_topic_path = self.publisher.topic_path(
                self.project_id,
                results_topic_name
            )
            
            # Create message
            message_data = {
                'job_id': job_id,
                'status': status,
                'results': results
            }
            
            message_json = json.dumps(message_data)
            message_bytes = message_json.encode('utf-8')
            
            # Publish
            future = self.publisher.publish(results_topic_path, message_bytes)
            message_id = future.result()
            
            logger.info(f"Published result: {job_id} -> {status}")
            
        except Exception as e:
            logger.error(f"Error publishing result: {str(e)}")
            # Don't raise - result publishing is non-critical
