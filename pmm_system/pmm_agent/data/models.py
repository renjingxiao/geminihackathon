"""Data models for PMM system"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MetricType(str, Enum):
    """Metric types"""
    RESPONSE_ACCURACY = "response_accuracy"
    HALLUCINATION_RATE = "hallucination_rate"
    PRIVACY_INCIDENTS = "privacy_incidents"
    USER_SATISFACTION = "user_satisfaction"
    PROMPT_INJECTION_ATTEMPTS = "prompt_injection_attempts"
    CITATION_ACCURACY = "citation_accuracy"


@dataclass
class AIInteraction:
    """AI system interaction record"""
    interaction_id: str
    timestamp: datetime
    user_id: Optional[str]
    prompt: str
    response: str
    response_time: float
    model_version: str
    metadata: Dict = field(default_factory=dict)
    demographics: Optional[Dict] = None


@dataclass
class SafetyThreshold:
    """Safety threshold configuration"""
    metric_name: str
    target: float
    alert_threshold: float
    critical_threshold: float


@dataclass
class MonitoringAlert:
    """Monitoring alert"""
    alert_id: str
    timestamp: datetime
    alert_type: str
    severity: AlertSeverity
    metric_name: str
    current_value: float
    threshold: float
    details: Dict = field(default_factory=dict)


@dataclass
class UserFeedback:
    """User feedback record"""
    feedback_id: str
    interaction_id: str
    user_id: Optional[str]
    timestamp: datetime
    rating: int  # 1-5
    comment: Optional[str]
    issues: List[str] = field(default_factory=list)
    sentiment: Optional[str] = None
    categories: List[str] = field(default_factory=list)


@dataclass
class MetricRecord:
    """Metric record for time series"""
    metric_name: str
    value: float
    timestamp: datetime
    tags: Dict = field(default_factory=dict)


@dataclass
class MonitoringPlan:
    """Monitoring plan configuration"""
    system_name: str
    metrics: Dict[str, SafetyThreshold]
    collection_methods: Dict
    reporting_cadence: str
    alert_thresholds: Dict
    created_at: datetime = field(default_factory=datetime.utcnow)
