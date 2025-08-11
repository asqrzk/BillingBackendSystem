import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.config import settings
from .base_service import BaseService


class QueueService(BaseService):
    """Service for managing Redis-based message queues."""
    
    async def queue_message(self, queue_name: str, message: Dict[str, Any], delay_seconds: int = 0):
        """Queue a message with optional delay."""
        try:
            if delay_seconds > 0:
                await self.redis.queue_delayed_message(queue_name, message, delay_seconds)
            else:
                await self.redis.queue_message(queue_name, message)
            
            self.logger.debug(f"Message queued",
                            queue=queue_name,
                            delay=delay_seconds,
                            message_id=message.get("id"))
        
        except Exception as e:
            self.logger.error(f"Error queuing message: {e}")
            raise
    
    async def process_delayed_queues(self):
        """Process delayed messages that are ready."""
        delayed_queues = [
            "queue:payment_initiation",
            "queue:payment_webhook_processing", 
            "queue:subscription_renewal",
            "queue:plan_change",
            "queue:usage_sync",
            "queue:renewal_retry"
        ]
        
        try:
            total_processed = 0
            
            for queue_name in delayed_queues:
                ready_messages = await self.redis.get_ready_delayed_messages(queue_name)
                
                for message_str in ready_messages:
                    # Move to primary queue
                    await self.redis.queue_message(queue_name, json.loads(message_str))
                    total_processed += 1
            
            if total_processed > 0:
                self.logger.info(f"Processed delayed messages", count=total_processed)
            
            return total_processed
        
        except Exception as e:
            self.logger.error(f"Error processing delayed queues: {e}")
            raise
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics for all queues."""
        try:
            queue_names = [
                "queue:payment_initiation",
                "queue:trial_payment",
                "queue:payment_webhook_processing",
                "queue:subscription_renewal", 
                "queue:plan_change",
                "queue:usage_sync",
                "queue:renewal_retry"
            ]
            
            stats = {}
            total_depth = 0
            
            for queue_name in queue_names:
                depth = await self.redis.get_queue_length(queue_name)
                delayed_depth = await self.redis.get_queue_length(f"{queue_name}:delayed")
                failed_depth = await self.redis.get_queue_length(f"{queue_name}:failed")
                
                stats[queue_name] = {
                    "active_depth": depth,
                    "delayed_depth": delayed_depth,
                    "failed_depth": failed_depth,
                    "total_depth": depth + delayed_depth + failed_depth
                }
                
                total_depth += stats[queue_name]["total_depth"]
            
            stats["summary"] = {
                "total_queues": len(queue_names),
                "total_depth": total_depth,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return stats
        
        except Exception as e:
            self.logger.error(f"Error getting queue stats: {e}")
            raise
    
    async def retry_failed_messages(self, queue_name: str, max_retries: int = None) -> int:
        """Retry failed messages from dead letter queue."""
        try:
            failed_queue = f"{queue_name}:failed"
            
            # Get all failed messages (this is a list operation)
            failed_messages = []
            
            # In a real implementation, you'd want to use LRANGE to get messages
            # For now, we'll implement a simple approach
            retried_count = 0
            
            # This is a simplified version - in production you'd want to:
            # 1. Get messages from failed queue
            # 2. Check if they should be retried
            # 3. Move them back to main queue or delayed queue
            
            self.logger.info(f"Retry operation completed",
                           queue=queue_name,
                           retried_count=retried_count)
            
            return retried_count
        
        except Exception as e:
            self.logger.error(f"Error retrying failed messages: {e}")
            raise
    
    async def clear_queue(self, queue_name: str, include_delayed: bool = False, include_failed: bool = False) -> Dict[str, int]:
        """Clear messages from a queue."""
        try:
            cleared_counts = {}
            
            # Clear main queue
            if self.redis.client:
                cleared_counts["active"] = await self.redis.client.delete(queue_name)
                
                if include_delayed:
                    cleared_counts["delayed"] = await self.redis.client.delete(f"{queue_name}:delayed")
                
                if include_failed:
                    cleared_counts["failed"] = await self.redis.client.delete(f"{queue_name}:failed")
            
            self.logger.info(f"Queue cleared",
                           queue=queue_name,
                           cleared_counts=cleared_counts)
            
            return cleared_counts
        
        except Exception as e:
            self.logger.error(f"Error clearing queue: {e}")
            raise
    
    async def peek_queue_messages(self, queue_name: str, count: int = 10) -> List[Dict[str, Any]]:
        """Peek at messages in a queue without removing them."""
        try:
            if not self.redis.client:
                return []
            
            # Use LRANGE to peek at messages
            message_strings = await self.redis.client.lrange(queue_name, 0, count - 1)
            messages = []
            
            for msg_str in message_strings:
                try:
                    messages.append(json.loads(msg_str))
                except json.JSONDecodeError:
                    self.logger.warning(f"Invalid JSON in queue message", queue=queue_name)
            
            return messages
        
        except Exception as e:
            self.logger.error(f"Error peeking queue messages: {e}")
            raise
    
    async def move_message_to_failed(self, queue_name: str, message: Dict[str, Any], error_message: str):
        """Move a message to the failed queue."""
        try:
            failed_message = {
                **message,
                "failed_at": datetime.utcnow().isoformat(),
                "error_message": error_message,
                "original_queue": queue_name
            }
            
            failed_queue = f"{queue_name}:failed"
            await self.redis.queue_message(failed_queue, failed_message)
            
            self.logger.warning(f"Message moved to failed queue",
                              queue=queue_name,
                              error=error_message,
                              message_id=message.get("id"))
        
        except Exception as e:
            self.logger.error(f"Error moving message to failed queue: {e}")
            raise
    
    async def schedule_renewal_check(self):
        """Schedule renewal check for expiring subscriptions."""
        try:
            # This would typically be called by a cron job
            renewal_check_message = {
                "task": "renewal_check",
                "scheduled_at": datetime.utcnow().isoformat(),
                "retry_count": 0,
                "max_retries": 1
            }
            
            await self.redis.queue_message("queue:subscription_renewal_check", renewal_check_message)
            
            self.logger.info("Renewal check scheduled")
        
        except Exception as e:
            self.logger.error(f"Error scheduling renewal check: {e}")
            raise 