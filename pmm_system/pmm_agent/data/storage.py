"""Data storage layer - simplified in-memory implementation"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import json
from pathlib import Path

from .models import AIInteraction, MonitoringAlert, UserFeedback, MetricRecord


class InMemoryStorage:
    """In-memory storage for development/testing"""

    def __init__(self):
        self.interactions: List[AIInteraction] = []
        self.alerts: List[MonitoringAlert] = []
        self.feedback: List[UserFeedback] = []
        self.metrics: Dict[str, List[MetricRecord]] = defaultdict(list)
        self.storage_path = Path("pmm_data")
        self.storage_path.mkdir(exist_ok=True)

    def store_interaction(self, interaction: AIInteraction):
        """Store an interaction"""
        self.interactions.append(interaction)
        self._persist_to_file("interactions")

    def store_alert(self, alert: MonitoringAlert):
        """Store an alert"""
        self.alerts.append(alert)
        self._persist_to_file("alerts")

    def store_feedback(self, feedback: UserFeedback):
        """Store user feedback"""
        self.feedback.append(feedback)
        self._persist_to_file("feedback")

    def store_metric(self, metric: MetricRecord):
        """Store a metric"""
        self.metrics[metric.metric_name].append(metric)
        self._persist_to_file(f"metrics_{metric.metric_name}")

    def get_interactions(self,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> List[AIInteraction]:
        """Get interactions in time range"""
        if not start_time:
            start_time = datetime.min
        if not end_time:
            end_time = datetime.now(timezone.utc)

        return [i for i in self.interactions
                if start_time <= i.timestamp <= end_time]

    def get_metrics(self,
                   metric_name: str,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None) -> List[MetricRecord]:
        """Get metrics in time range"""
        if not start_time:
            start_time = datetime.min
        if not end_time:
            end_time = datetime.now(timezone.utc)

        metrics = self.metrics.get(metric_name, [])
        return [m for m in metrics
                if start_time <= m.timestamp <= end_time]

    def get_active_alerts(self) -> List[MonitoringAlert]:
        """Get active alerts (last 24 hours)"""
        threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        return [a for a in self.alerts if a.timestamp >= threshold]

    def get_recent_feedback(self, days: int = 7) -> List[UserFeedback]:
        """Get recent feedback"""
        threshold = datetime.now(timezone.utc) - timedelta(days=days)
        return [f for f in self.feedback if f.timestamp >= threshold]

    def _persist_to_file(self, data_type: str):
        """Persist data to JSON file"""
        try:
            file_path = self.storage_path / f"{data_type}.json"

            if data_type == "interactions":
                data = [self._serialize_interaction(i) for i in self.interactions[-100:]]
            elif data_type == "alerts":
                data = [self._serialize_alert(a) for a in self.alerts[-100:]]
            elif data_type == "feedback":
                data = [self._serialize_feedback(f) for f in self.feedback[-100:]]
            elif data_type.startswith("metrics_"):
                metric_name = data_type.replace("metrics_", "")
                data = [self._serialize_metric(m) for m in self.metrics[metric_name][-100:]]
            else:
                return

            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"Warning: Failed to persist {data_type}: {e}")

    @staticmethod
    def _serialize_interaction(interaction: AIInteraction) -> dict:
        return {
            "interaction_id": interaction.interaction_id,
            "timestamp": interaction.timestamp.isoformat(),
            "user_id": interaction.user_id,
            "prompt": interaction.prompt[:100],  # Truncate for storage
            "response": interaction.response[:200],
            "response_time": interaction.response_time,
            "model_version": interaction.model_version
        }

    @staticmethod
    def _serialize_alert(alert: MonitoringAlert) -> dict:
        return {
            "alert_id": alert.alert_id,
            "timestamp": alert.timestamp.isoformat(),
            "alert_type": alert.alert_type,
            "severity": alert.severity.value,
            "metric_name": alert.metric_name,
            "current_value": alert.current_value,
            "threshold": alert.threshold
        }

    @staticmethod
    def _serialize_feedback(feedback: UserFeedback) -> dict:
        return {
            "feedback_id": feedback.feedback_id,
            "interaction_id": feedback.interaction_id,
            "timestamp": feedback.timestamp.isoformat(),
            "rating": feedback.rating,
            "sentiment": feedback.sentiment,
            "categories": feedback.categories
        }

    @staticmethod
    def _serialize_metric(metric: MetricRecord) -> dict:
        return {
            "metric_name": metric.metric_name,
            "value": metric.value,
            "timestamp": metric.timestamp.isoformat(),
            "tags": metric.tags
        }


# Global storage instance
storage = InMemoryStorage()
