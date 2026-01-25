"""
Data models for Article 12 Logging & Traceability System.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class LogEntry:
    """Operational Log Entry (Sheet: 2. Operational Logs)"""
    log_id: str
    timestamp_start: datetime
    timestamp_end: datetime
    event_type: str  # Normal Operation
    system_version: str
    input_hash: str
    output_hash: str


@dataclass
class RiskEntry:
    """Risk & Incident Log Entry (Sheet: 3. Risk & Incident Logs)"""
    log_id: str
    timestamp: datetime
    event_type: str  # Risk/Incident/Modification
    risk_category: str  # Art 79 categories
    description: str
    automated_alert: bool
    action_taken: str


@dataclass
class CapabilityEntry:
    """Capability Checklist Entry (Sheet: 1. Capability Checklist)"""
    requirement: str
    description: str
    status: str  # Compliant/Not Compliant
    implementation_details: str


@dataclass
class BiometricEntry:
    """Biometric Specifics Entry (Sheet: 4. Biometric Specifics)"""
    requirement: str  # Annex III 1(a)
    log_field_name: str
    data_format: str
    retention_period: str  # >6 Months
