import json
import time
from typing import Any, Dict, List, Optional, Union
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis client for queue management and atomic operations.
    """
    
    def __init__(self):
        self.pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True
        )
        self.client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Initialize Redis connection."""
        try:
            self.client = redis.Redis(connection_pool=self.pool)
            # Test connection
            await self.client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            await self.client.aclose()
            logger.info("Redis connection closed")
    
    async def queue_message(self, queue_name: str, message: Dict[str, Any]):
        """Add message to queue."""
        try:
            if not self.client:
                await self.connect()
            await self.client.lpush(queue_name, json.dumps(message, default=str))
            logger.debug(f"Message queued to {queue_name}")
        except Exception as e:
            logger.error(f"Failed to queue message to {queue_name}: {e}")
            raise
    
    async def claim_message(self, main_queue: str, processing_queue: str, timeout: int = 1) -> Optional[str]:
        """Atomically claim a message from main_queue into processing_queue (BRPOPLPUSH)."""
        try:
            if not self.client:
                await self.connect()
            msg = await self.client.brpoplpush(main_queue, processing_queue, timeout=timeout)
            return msg
        except Exception as e:
            logger.error(f"Failed to claim message from {main_queue}: {e}")
            return None
    
    async def remove_from_processing(self, processing_queue: str, message_json: str) -> int:
        """Remove a specific message from processing queue (LREM)."""
        try:
            if not self.client:
                await self.connect()
            return await self.client.lrem(processing_queue, 1, message_json)
        except Exception as e:
            logger.error(f"Failed to remove from {processing_queue}: {e}")
            return 0
    
    async def queue_delayed_message(self, queue_name: str, message: Dict[str, Any], delay_seconds: int):
        """Add message to delayed queue (ZSET with timestamp score)."""
        try:
            if not self.client:
                await self.connect()
            delayed_queue = f"{queue_name}:delayed"
            score = time.time() + delay_seconds
            await self.client.zadd(delayed_queue, {json.dumps(message, default=str): score})
            logger.debug(f"Delayed message queued to {delayed_queue} with delay {delay_seconds}s")
        except Exception as e:
            logger.error(f"Failed to queue delayed message: {e}")
            raise
    
    async def move_ready_delayed_to_main(self, queue_name: str) -> int:
        """Move ready messages from delayed zset back to main queue."""
        try:
            if not self.client:
                await self.connect()
            delayed_queue = f"{queue_name}:delayed"
            now = time.time()
            messages = await self.client.zrangebyscore(delayed_queue, 0, now)
            moved = 0
            for msg in messages:
                await self.client.lpush(queue_name, msg)
                moved += 1
            if messages:
                await self.client.zremrangebyscore(delayed_queue, 0, now)
            return moved
        except Exception as e:
            logger.error(f"Failed moving delayed for {queue_name}: {e}")
            return 0
    
    async def get_ready_delayed_messages(self, queue_name: str) -> List[str]:
        """Get messages from delayed queue that are ready to process."""
        try:
            if not self.client:
                await self.connect()
            delayed_queue = f"{queue_name}:delayed"
            current_time = time.time()
            
            # Get ready messages
            messages = await self.client.zrangebyscore(delayed_queue, 0, current_time)
            
            if messages:
                # Remove them from delayed queue
                await self.client.zremrangebyscore(delayed_queue, 0, current_time)
                logger.debug(f"Retrieved {len(messages)} ready messages from {delayed_queue}")
            
            return messages
        except Exception as e:
            logger.error(f"Failed to get ready delayed messages: {e}")
            return []
    
    async def set_lock(self, lock_key: str, ttl_seconds: int = 300) -> bool:
        """
        Set a distributed lock.
        Returns True if lock acquired, False if already exists.
        """
        try:
            if not self.client:
                await self.connect()
            result = await self.client.set(lock_key, "1", nx=True, ex=ttl_seconds)
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to set lock {lock_key}: {e}")
            return False
    
    async def release_lock(self, lock_key: str):
        """Release a distributed lock."""
        try:
            if not self.client:
                await self.connect()
            await self.client.delete(lock_key)
        except Exception as e:
            logger.error(f"Failed to release lock {lock_key}: {e}")
    
    async def get_queue_length(self, queue_name: str) -> int:
        """Get length of a queue."""
        try:
            if not self.client:
                await self.connect()
            return await self.client.llen(queue_name)
        except Exception as e:
            logger.error(f"Failed to get queue length for {queue_name}: {e}")
            return 0


# Global Redis client instance
redis_client = RedisClient() 