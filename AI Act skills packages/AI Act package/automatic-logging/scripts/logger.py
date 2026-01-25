"""
Compliance Logger - Core middleware for Article 12 Logging.
"""
import functools
import time
from datetime import datetime
from typing import Callable, Any, Optional

from models import LogEntry, RiskEntry
from utils import (
    generate_uuid, hash_text, format_timestamp,
    ensure_csvs_initialized, append_to_csv,
    OPERATIONAL_CSV, RISK_CSV
)


class ComplianceLogger:
    """
    Core logging middleware for AI Act Article 12 compliance.
    
    Usage:
        logger = ComplianceLogger(system_version="v1.0.0")
        logger.log_operation(input_text, output_text, start_time, end_time)
    """
    
    def __init__(self, system_version: str = "1.0.0"):
        self.system_version = system_version
        ensure_csvs_initialized()
    
    def log_operation(
        self,
        input_text: str,
        output_text: str,
        start_time: datetime,
        end_time: datetime,
        event_type: str = "Normal Operation"
    ) -> str:
        """
        Log an AI operation to Operational_Logs.
        Returns the log_id.
        """
        log_id = generate_uuid()
        
        row = [
            log_id,
            format_timestamp(start_time),
            format_timestamp(end_time),
            event_type,
            self.system_version,
            hash_text(input_text),
            hash_text(output_text)
        ]
        
        append_to_csv(OPERATIONAL_CSV, row)
        return log_id
    
    def log_risk(
        self,
        event_type: str,
        risk_category: str,
        description: str,
        action_taken: str = "",
        automated_alert: bool = True,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Log a risk/incident event to Risk_Logs.
        Returns the log_id.
        """
        log_id = generate_uuid()
        ts = timestamp or datetime.now()
        
        row = [
            log_id,
            format_timestamp(ts),
            event_type,
            risk_category,
            description,
            "Yes" if automated_alert else "No",
            action_taken
        ]
        
        append_to_csv(RISK_CSV, row)
        return log_id


# Global logger instance
_default_logger: Optional[ComplianceLogger] = None


def get_logger(system_version: str = "1.0.0") -> ComplianceLogger:
    """Get or create the default logger instance."""
    global _default_logger
    if _default_logger is None:
        _default_logger = ComplianceLogger(system_version)
    return _default_logger


def log_interaction(func: Callable = None, *, system_version: str = "1.0.0"):
    """
    Decorator to automatically log AI interactions.
    
    Usage:
        @log_interaction
        def chat_with_ai(user_input: str) -> str:
            # ... AI logic ...
            return response
        
        @log_interaction(system_version="2.0.0")
        def process_query(query: str) -> str:
            return "result"
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> Any:
            logger = get_logger(system_version)
            
            # Capture input (first arg or 'input' kwarg)
            input_text = ""
            if args:
                input_text = str(args[0])
            elif 'input' in kwargs:
                input_text = str(kwargs['input'])
            elif 'query' in kwargs:
                input_text = str(kwargs['query'])
            elif 'user_input' in kwargs:
                input_text = str(kwargs['user_input'])
            
            start_time = datetime.now()
            
            try:
                result = fn(*args, **kwargs)
                end_time = datetime.now()
                
                output_text = str(result) if result else ""
                logger.log_operation(input_text, output_text, start_time, end_time)
                
                # Import watchdog here to avoid circular imports
                from watchdog import check_operation
                check_operation(start_time, end_time, logger)
                
                return result
            except Exception as e:
                end_time = datetime.now()
                logger.log_risk(
                    event_type="Incident",
                    risk_category="System Error",
                    description=f"Exception in {fn.__name__}: {str(e)}",
                    action_taken="Logged and re-raised"
                )
                raise
        
        return wrapper
    
    if func is not None:
        return decorator(func)
    return decorator
