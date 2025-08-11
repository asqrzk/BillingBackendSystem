from celery import Celery
from app.core.config import settings

# Create Celery instance for the payment service
celery_app = Celery(
    "payment_service",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        'app.workers.tasks',
    ]
)

# Basic Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing - route all payment service tasks to payment_tasks queue
    task_routes={
        'app.workers.tasks.*': {'queue': 'payment_tasks'},
    },
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'process-webhook-queue': {
            'task': 'app.workers.tasks.process_webhook_processing',
            'schedule': 10.0,  # Every 10 seconds
        },
        'process-refund-queue': {
            'task': 'app.workers.tasks.process_refund_initiation',
            'schedule': 15.0,  # Every 15 seconds
        },
        'pump-delayed-queues': {
            'task': 'app.workers.tasks.pump_delayed_queues',
            'schedule': 5.0,  # Move ready delayed → main frequently
        },
        'sweep-processing-queues': {
            'task': 'app.workers.tasks.sweep_processing_queues',
            'schedule': 20.0,  # Periodically return orphans to delayed/failed
        },
    },
    
    # Async task support
    task_always_eager=False,
    task_eager_propagates=True,
    
    worker_concurrency=2,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
) 