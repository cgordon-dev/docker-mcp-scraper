import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import json
from functools import wraps


class MCPScraperLogger:
    """Production-ready logging system for MCP Scraper."""
    
    def __init__(self, name: str = "mcp_scraper", log_level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup console and file handlers with proper formatting."""
        
        # Console handler for development
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for production logs
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(
            log_dir / f"mcp_scraper_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Error file handler for critical issues
        error_handler = logging.FileHandler(
            log_dir / f"mcp_scraper_errors_{datetime.now().strftime('%Y%m%d')}.log"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        self.logger.addHandler(error_handler)
    
    def info(self, message: str, **kwargs):
        """Log info message with optional structured data."""
        if kwargs:
            message = f"{message} | {json.dumps(kwargs, default=str)}"
        self.logger.info(message)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with optional structured data."""
        if kwargs:
            message = f"{message} | {json.dumps(kwargs, default=str)}"
        self.logger.debug(message)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with optional structured data."""
        if kwargs:
            message = f"{message} | {json.dumps(kwargs, default=str)}"
        self.logger.warning(message)
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with optional exception and structured data."""
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['error_message'] = str(error)
        
        if kwargs:
            message = f"{message} | {json.dumps(kwargs, default=str)}"
        
        self.logger.error(message, exc_info=error is not None)
    
    def critical(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log critical message with optional exception and structured data."""
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['error_message'] = str(error)
        
        if kwargs:
            message = f"{message} | {json.dumps(kwargs, default=str)}"
        
        self.logger.critical(message, exc_info=error is not None)


# Global logger instance
logger = MCPScraperLogger()


def log_execution_time(func):
    """Decorator to log function execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        try:
            result = func(*args, **kwargs)
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.debug(
                f"Function {func.__name__} completed successfully",
                execution_time_seconds=execution_time
            )
            return result
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"Function {func.__name__} failed",
                error=e,
                execution_time_seconds=execution_time
            )
            raise
    return wrapper


def log_api_call(service: str, endpoint: str):
    """Decorator to log API calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            logger.debug(
                f"API call started",
                service=service,
                endpoint=endpoint,
                function=func.__name__
            )
            
            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.info(
                    f"API call successful",
                    service=service,
                    endpoint=endpoint,
                    execution_time_seconds=execution_time
                )
                return result
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"API call failed",
                    service=service,
                    endpoint=endpoint,
                    error=e,
                    execution_time_seconds=execution_time
                )
                raise
        return wrapper
    return decorator


class ScrapingError(Exception):
    """Base exception for scraping-related errors."""
    pass


class RegistryError(ScrapingError):
    """Registry-specific errors."""
    def __init__(self, message: str, registry: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.registry = registry
        self.status_code = status_code


class DockerError(ScrapingError):
    """Docker-related errors."""
    def __init__(self, message: str, image: str, operation: str):
        super().__init__(message)
        self.image = image
        self.operation = operation


class MCPProtocolError(ScrapingError):
    """MCP protocol-related errors."""
    def __init__(self, message: str, server: str, protocol_version: Optional[str] = None):
        super().__init__(message)
        self.server = server
        self.protocol_version = protocol_version


class ValidationError(ScrapingError):
    """Data validation errors."""
    def __init__(self, message: str, field: str, value: Any):
        super().__init__(message)
        self.field = field
        self.value = value