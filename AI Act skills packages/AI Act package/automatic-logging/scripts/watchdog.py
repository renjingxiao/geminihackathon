"""
AI Watchdog - Real-time anomaly detection for Article 12 compliance.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from collections import deque
import threading

# In-memory storage for frequency checking
_recent_calls: deque = deque(maxlen=100)
_lock = threading.Lock()

# Thresholds
LATENCY_THRESHOLD_SECONDS = 5.0
FREQUENCY_THRESHOLD_CALLS = 10
FREQUENCY_WINDOW_SECONDS = 1.0


def check_latency(
    start_time: datetime,
    end_time: datetime,
    logger: Optional["ComplianceLogger"] = None
) -> bool:
    """
    Check if operation latency exceeds threshold.
    Returns True if anomaly detected.
    """
    duration = (end_time - start_time).total_seconds()
    
    if duration > LATENCY_THRESHOLD_SECONDS:
        if logger:
            logger.log_risk(
                event_type="Risk",
                risk_category="Performance degradation / Availability Risk",
                description=f"High latency detected: {duration:.2f}s (threshold: {LATENCY_THRESHOLD_SECONDS}s)",
                action_taken="Automated alert generated",
                automated_alert=True
            )
        return True
    return False


def check_frequency(
    logger: Optional["ComplianceLogger"] = None
) -> bool:
    """
    Check if call frequency indicates potential DOS attack.
    Returns True if anomaly detected.
    """
    now = datetime.now()
    
    with _lock:
        # Add current call
        _recent_calls.append(now)
        
        # Count calls in the last window
        window_start = now - timedelta(seconds=FREQUENCY_WINDOW_SECONDS)
        recent_count = sum(1 for t in _recent_calls if t >= window_start)
    
    if recent_count >= FREQUENCY_THRESHOLD_CALLS:
        if logger:
            logger.log_risk(
                event_type="Risk",
                risk_category="Cybersecurity / Denial of Service",
                description=f"High frequency detected: {recent_count} calls in {FREQUENCY_WINDOW_SECONDS}s",
                action_taken="Automated alert generated",
                automated_alert=True
            )
        return True
    return False


def check_operation(
    start_time: datetime,
    end_time: datetime,
    logger: Optional["ComplianceLogger"] = None
) -> dict:
    """
    Run all watchdog checks on an operation.
    Returns dict with check results.
    """
    results = {
        "latency_alert": check_latency(start_time, end_time, logger),
        "frequency_alert": check_frequency(logger)
    }
    return results


def reset_frequency_tracker():
    """Reset the frequency tracker (useful for testing)."""
    global _recent_calls
    with _lock:
        _recent_calls.clear()
