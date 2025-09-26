"""
Logging configuration for FastAPI Traffic Prediction API
Provides structured logging with different handlers and formatters
"""

import os
import sys
import logging
import logging.handlers
from typing import Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

from .config import get_settings

settings = get_settings()


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        if hasattr(record, 'endpoint'):
            log_entry["endpoint"] = record.endpoint
        if hasattr(record, 'method'):
            log_entry["method"] = record.method
        if hasattr(record, 'status_code'):
            log_entry["status_code"] = record.status_code
        if hasattr(record, 'duration'):
            log_entry["duration"] = record.duration
        
        return json.dumps(log_entry)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        log_color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        
        formatted = super().format(record)
        return formatted


def setup_logging():
    """Setup logging configuration for the application"""
    
    # Create logs directory if it doesn't exist (simplified - no file logging for now)
    # log_dir = Path("logs")
    # log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Use simple console formatter for now
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Add console handler to root logger
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("kafka").setLevel(logging.INFO)
    
    # Suppress noisy loggers in production
    if settings.environment == "production":
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        logging.getLogger("requests.packages.urllib3").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured - Level: {settings.log_level}, JSON: False")


class RequestLoggingMiddleware:
    """Middleware for logging HTTP requests"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = datetime.utcnow()
        request_id = f"req_{int(start_time.timestamp() * 1000000)}"
        
        # Add request ID to scope for downstream use
        scope["request_id"] = request_id
        
        logger = logging.getLogger("api.requests")
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                extra = {
                    "request_id": request_id,
                    "method": scope["method"],
                    "path": scope["path"],
                    "status_code": status_code,
                    "duration": round(duration, 2),
                }
                
                if status_code >= 400:
                    logger.warning(f"HTTP {status_code} {scope['method']} {scope['path']}", extra=extra)
                else:
                    logger.info(f"HTTP {status_code} {scope['method']} {scope['path']}", extra=extra)
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)


class ContextualLogger:
    """Logger with contextual information"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """Set context for all subsequent log messages"""
        self._context.update(kwargs)
    
    def clear_context(self):
        """Clear all context"""
        self._context.clear()
    
    def debug(self, message: str, **kwargs):
        extra = {**self._context, **kwargs}
        self.logger.debug(message, extra=extra)
    
    def info(self, message: str, **kwargs):
        extra = {**self._context, **kwargs}
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        extra = {**self._context, **kwargs}
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, **kwargs):
        extra = {**self._context, **kwargs}
        self.logger.error(message, extra=extra)
    
    def critical(self, message: str, **kwargs):
        extra = {**self._context, **kwargs}
        self.logger.critical(message, extra=extra)


def get_logger(name: str) -> ContextualLogger:
    """Get a contextual logger instance"""
    return ContextualLogger(name)


# Application loggers
api_logger = get_logger("api")
db_logger = get_logger("database")
kafka_logger = get_logger("kafka")
websocket_logger = get_logger("websocket")
prediction_logger = get_logger("prediction")


class LoggingConfig:
    """Logging configuration utilities"""
    
    @staticmethod
    def log_startup_info():
        """Log application startup information"""
        logger = logging.getLogger("startup")
        
        logger.info("Starting Traffic Prediction API")
        logger.info(f"Environment: {settings.environment}")
        logger.info(f"Debug mode: {settings.debug}")
        logger.info(f"API Host: {settings.api_host}:{settings.api_port}")
        logger.info(f"Database: {settings.db_host}:{settings.db_port}")
        logger.info(f"Kafka: ['localhost:9092']")
        logger.info(f"Log level: {settings.log_level}")
    
    @staticmethod
    def log_shutdown_info():
        """Log application shutdown information"""
        logger = logging.getLogger("shutdown")
        logger.info("Shutting down Traffic Prediction API")
    
    @staticmethod
    def get_log_stats() -> Dict[str, Any]:
        """Get logging statistics"""
        handlers_info = []
        
        for handler in logging.getLogger().handlers:
            handler_info = {
                "type": type(handler).__name__,
                "level": logging.getLevelName(handler.level),
                "formatter": type(handler.formatter).__name__ if handler.formatter else None
            }
            
            # Skip file handler info for now
            # if hasattr(handler, 'baseFilename'):
            #     handler_info["file"] = handler.baseFilename
            
            handlers_info.append(handler_info)
        
        return {
            "root_level": logging.getLevelName(logging.getLogger().level),
            "handlers": handlers_info,
            "json_logs": False,
            "request_logging": True
        }


# Initialize logging when module is imported
_logging_initialized = False
if not _logging_initialized:
    setup_logging()
    _logging_initialized = True