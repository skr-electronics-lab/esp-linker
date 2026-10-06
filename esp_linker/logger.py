"""
ESP-Linker Logging Configuration
(c) 2025 SK Raihan / SKR Electronics Lab -- All Rights Reserved.

Centralized logging configuration for ESP-Linker library
"""

import logging
import sys
from typing import Optional

# Default log format
DEFAULT_FORMAT = '[%(asctime)s] %(levelname)s - %(name)s: %(message)s'
SIMPLE_FORMAT = '[%(levelname)s] %(message)s'

class ESPLinkerLogger:
    """Centralized logger for ESP-Linker"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ESPLinkerLogger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.setup_logging()
            self._initialized = True
    
    def setup_logging(self, level: int = logging.INFO, format_str: str = SIMPLE_FORMAT):
        """Setup logging configuration"""
        # Create root logger for esp_linker
        self.logger = logging.getLogger('esp_linker')
        self.logger.setLevel(level)
        
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter(format_str)
        handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def get_logger(self, name: str = 'esp_linker') -> logging.Logger:
        """Get a logger instance"""
        return logging.getLogger(name)
    
    def set_level(self, level: int):
        """Set logging level"""
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)

# Global logger instance
_logger_instance = ESPLinkerLogger()

def get_logger(name: str = 'esp_linker') -> logging.Logger:
    """Get a logger instance for ESP-Linker"""
    return _logger_instance.get_logger(name)

def set_log_level(level: int):
    """Set global logging level"""
    _logger_instance.set_level(level)

def setup_logging(level: int = logging.INFO, format_str: str = SIMPLE_FORMAT):
    """Setup logging configuration"""
    _logger_instance.setup_logging(level, format_str)

# Convenience functions for different log levels
def debug(message: str, logger_name: str = 'esp_linker'):
    """Log debug message"""
    get_logger(logger_name).debug(message)

def info(message: str, logger_name: str = 'esp_linker'):
    """Log info message"""
    get_logger(logger_name).info(message)

def warning(message: str, logger_name: str = 'esp_linker'):
    """Log warning message"""
    get_logger(logger_name).warning(message)

def error(message: str, logger_name: str = 'esp_linker'):
    """Log error message"""
    get_logger(logger_name).error(message)

def critical(message: str, logger_name: str = 'esp_linker'):
    """Log critical message"""
    get_logger(logger_name).critical(message)

# Initialize logging on import
setup_logging()
