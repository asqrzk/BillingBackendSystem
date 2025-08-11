import json
import asyncio
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.redis_client import redis_client
from app.core.logging import get_logger
from app.core.config import settings


class BaseConsumer:
    """Base class for all Celery consumers."""
    
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.logger = get_logger(self.__class__.__name__)
        self.redis = redis_client
    
    async def get_session(self) -> AsyncSession:
        """Get database session for worker."""
        async for session in get_async_session():
            return session
    
    async def process_message(self, message_data: Dict[str, Any]) -> bool:
        """
        Process a single message. Override in subclasses.
        
        Returns:
            bool: True if successful, False if should retry
        """
        raise NotImplementedError("Subclasses must implement process_message")
    
    async def handle_retry(self, message_data: Dict[str, Any], error: Exception):
        """Handle message retry logic."""
        retry_count = message_data.get("retry_count", 0)
        max_retries = message_data.get("max_retries", 3)
        
        if retry_count < max_retries:
            # Increment retry count
            message_data["retry_count"] = retry_count + 1
            
            # Calculate delay (exponential backoff)
            delay = min(300 * (2 ** retry_count), 1800)  # Max 30 minutes
            
            # Queue for delayed retry
            await self.redis.queue_delayed_message(
                self.queue_name, 
                message_data, 
                delay
            )
            
            self.logger.warning(f"Message queued for retry",
                              retry_count=retry_count + 1,
                              max_retries=max_retries,
                              delay=delay,
                              error=str(error))
        else:
            # Move to failed queue
            failed_message = {
                **message_data,
                "failed_at": "2024-01-01T00:00:00Z",  # Would use datetime.utcnow()
                "error_message": str(error),
                "original_queue": self.queue_name
            }
            
            await self.redis.queue_message(f"{self.queue_name}:failed", failed_message)
            
            self.logger.error(f"Message moved to failed queue",
                            retry_count=retry_count,
                            error=str(error))
    
    async def run_consumer(self):
        """Main consumer loop."""
        self.logger.info(f"Starting consumer for queue: {self.queue_name}")
        
        while True:
            try:
                # Use blocking pop with timeout
                result = await self.redis.client.brpop(self.queue_name, timeout=10)
                
                if not result:
                    continue  # Timeout, continue loop
                
                # Parse message
                queue, message_str = result
                message_data = json.loads(message_str)
                
                try:
                    # Process the message
                    success = await self.process_message(message_data)
                    
                    if success:
                        self.logger.debug(f"Message processed successfully",
                                        queue=self.queue_name)
                    else:
                        # Processing failed, handle retry
                        await self.handle_retry(message_data, Exception("Processing failed"))
                
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}",
                                    queue=self.queue_name,
                                    message=message_data)
                    
                    # Handle retry for processing errors
                    await self.handle_retry(message_data, e)
            
            except Exception as e:
                self.logger.error(f"Error in consumer loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    def run_sync_consumer(self):
        """Synchronous wrapper for async consumer (for Celery)."""
        asyncio.run(self.run_consumer()) 