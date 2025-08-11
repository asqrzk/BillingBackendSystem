from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "subscription_service",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        'app.workers.subscription_consumer',
        'app.workers.usage_consumer', 
        'app.workers.webhook_consumer',
        'app.workers.queue_processor'
    ]
)

# Configure Celery
celery_app.conf.update(
    # Task serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'app.workers.subscription_consumer.*': {'queue': 'subscription_tasks'},
        'app.workers.usage_consumer.*': {'queue': 'usage_tasks'},
        'app.workers.webhook_consumer.*': {'queue': 'webhook_tasks'},
        'app.workers.queue_processor.*': {'queue': 'queue_tasks'},
    },
    
    # Worker configuration
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # Process Redis queues every 10 seconds
        "process-payment-initiation-queue": {
            "task": "app.workers.queue_processor.poll_payment_initiation_queue",
            "schedule": 10.0,  # Every 10 seconds
        },
        "process-trial-payment-queue": {
            "task": "app.workers.queue_processor.poll_trial_payment_queue", 
            "schedule": 10.0,  # Every 10 seconds
        },
        "process-plan-change-queue": {
            "task": "app.workers.queue_processor.poll_plan_change_queue",
            "schedule": 10.0,  # Every 10 seconds
        },
        "process-usage-sync-queue": {
            "task": "app.workers.queue_processor.poll_usage_sync_queue",
            "schedule": 15.0,  # Every 15 seconds
        },
        "process-webhook-queue": {
            "task": "app.workers.queue_processor.poll_webhook_processing_queue",
            "schedule": 10.0,  # Every 10 seconds
        },
        
        # Pump delayed queues frequently
        "pump-delayed-queues": {
            "task": "app.workers.queue_processor.process_delayed_queues",
            "schedule": 5.0,
        },
        
        # Scheduled maintenance tasks
        "renewal-scheduler": {
            "task": "app.workers.subscription_consumer.schedule_renewals",
            "schedule": crontab(hour=1, minute=0),  # Daily at 1 AM
        },
        "usage-sync-scheduler": {
            "task": "app.workers.usage_consumer.sync_usage_to_database",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
        },
        "usage-reset-scheduler": {
            "task": "app.workers.usage_consumer.reset_expired_usage",
            "schedule": crontab(hour=0, minute=0),  # Daily at midnight
        },
        "queue-cleanup": {
            "task": "app.workers.queue_processor.cleanup_old_queue_messages",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
        },
        "queue-health-monitor": {
            "task": "app.workers.queue_processor.monitor_queue_health",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
        "sweep-processing-queues": {
            "task": "app.workers.queue_processor.sweep_processing_queues",
            "schedule": 20.0,
        },
    },
)

# Import tasks to register them
from app.workers import subscription_consumer, usage_consumer, webhook_consumer, queue_processor 