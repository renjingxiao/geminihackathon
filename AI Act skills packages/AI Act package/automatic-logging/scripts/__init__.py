"""
__init__.py for automatic-logging scripts package.
"""
from models import LogEntry, RiskEntry, CapabilityEntry, BiometricEntry
from utils import (
    hash_text, generate_uuid, ensure_csvs_initialized,
    consolidate_to_excel, OUTPUT_DIR
)
from logger import ComplianceLogger, log_interaction, get_logger
from watchdog import check_latency, check_frequency, check_operation
from auditor import audit_logs

__all__ = [
    # Models
    "LogEntry", "RiskEntry", "CapabilityEntry", "BiometricEntry",
    # Utils
    "hash_text", "generate_uuid", "ensure_csvs_initialized",
    "consolidate_to_excel", "OUTPUT_DIR",
    # Logger
    "ComplianceLogger", "log_interaction", "get_logger",
    # Watchdog
    "check_latency", "check_frequency", "check_operation",
    # Auditor
    "audit_logs",
]
