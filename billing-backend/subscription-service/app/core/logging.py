import logging
import sys
from typing import Any, Dict
import structlog
from pythonjsonlogger import jsonlogger

from app.core.config import settings


def setup_logging():
    """
    Configure structured logging for the application.
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL),
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


class ContextLogger:
    """
    Logger with context support for tracing requests and operations.
    """
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
    
    def with_context(self, **kwargs) -> structlog.BoundLogger:
        """Add context to logger."""
        return self.logger.bind(**kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self.logger.info(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self.logger.error(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self.logger.warning(message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self.logger.debug(message, **kwargs)


def get_logger(name: str) -> ContextLogger:
    """
    Get a context-aware logger instance.
    """
    return ContextLogger(name) 