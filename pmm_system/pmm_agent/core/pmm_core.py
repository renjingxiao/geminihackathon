"""
PMM Core Agent - Main coordinator
"""
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from collections import defaultdict

from ..data.models import (
    AIInteraction, MonitoringAlert, UserFeedback,
    MetricRecord, AlertSeverity
)
from ..data.storage import storage
from ..integrations.safety_provider import SafetyMetricsProvider
from ..integrations.ethics_bridge import EthicsMonitoringBridge
from ..integrations.incident_trigger import IncidentTrigger


class PMMCoreAgent:
    """
    Post-Market Monitoring Core Agent

    Coordinates all monitoring functions and integrations
    """

    def __init__(self):
        # Initialize integrations
        self.safety_provider = SafetyMetricsProvider()
        self.ethics_bridge = EthicsMonitoringBridge()
        self.incident_trigger = IncidentTrigger()

        # Metrics buffer for recent calculations
        self.metrics_buffer = defaultdict(list)
        self.buffer_size = 100

        print("✓ PMM Core Agent initialized")
        print(f"  - {len(self.safety_provider.get_all_thresholds())} safety metrics configured")
        print("  - Ethics monitoring enabled")
        print("  - Incident response ready")

    async def process_interaction(self, interaction: AIInteraction) -> Dict:
        """
        Process a single AI interaction

        Workflow:
        1. Store interaction
        2. Extract metrics
        3. Check thresholds
        4. Bias monitoring (if demographics provided)
        5. Trigger alerts/incidents if needed

        Args:
            interaction: AI interaction to process

        Returns:
            Processing summary
        """
        # 1. Store interaction
        storage.store_interaction(interaction)

        # 2. Extract metrics
        metrics = await self._extract_metrics(interaction)

        # 3. Store and buffer metrics
        for metric_name, value in metrics.items():
            metric_record = MetricRecord(
                metric_name=metric_name,
                value=value,
                timestamp=interaction.timestamp,
                tags={'user_id': interaction.user_id or 'anonymous'}
            )
            storage.store_metric(metric_record)

            # Update buffer
            self.metrics_buffer[metric_name].append(value)
            if len(self.metrics_buffer[metric_name]) > self.buffer_size:
                self.metrics_buffer[metric_name].pop(0)

        # 4. Check thresholds
        alerts = []
        for metric_name, value in metrics.items():
            violation = self.safety_provider.check_threshold(metric_name, value)
            if violation:
                severity = AlertSeverity.CRITICAL if violation == 'critical' else AlertSeverity.HIGH
                alert = MonitoringAlert(
                    alert_id=f"ALT-{datetime.now(timezone.utc).timestamp()}",
                    timestamp=datetime.now(timezone.utc),
                    alert_type=f"{metric_name}_threshold_violation",
                    severity=severity,
                    metric_name=metric_name,
                    current_value=value,
                    threshold=self.safety_provider.get_threshold(metric_name).alert_threshold,
                    details={'interaction_id': interaction.interaction_id}
                )
                alerts.append(alert)
                storage.store_alert(alert)
                print(f"⚠️  Alert: {metric_name} = {value:.3f} (threshold: {alert.threshold:.3f})")

        # 5. Bias monitoring
        bias_alerts = []
        ethics_assessment = None
        if interaction.demographics:
            self.ethics_bridge.log_interaction(interaction)
            bias_alerts = self.ethics_bridge.check_bias_alerts()

            if bias_alerts and self.ethics_bridge.should_trigger_ethics_assessment(bias_alerts):
                ethics_assessment = await self.ethics_bridge.trigger_ethics_assessment(bias_alerts)
                print(f"📊 Ethics assessment triggered: {ethics_assessment['assessment_tier']}")

        # 6. Create incidents for critical alerts
        incidents = []
        for alert in alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                incident_id = self.incident_trigger.create_incident(
                    alert=alert,
                    context={
                        'user_id': interaction.user_id,
                        'model_version': interaction.model_version,
                        'response_time': interaction.response_time
                    }
                )
                incidents.append(incident_id)

        # Return processing summary
        return {
            'interaction_id': interaction.interaction_id,
            'metrics_computed': len(metrics),
            'alerts_triggered': len(alerts),
            'bias_alerts': len(bias_alerts),
            'incidents_created': len(incidents),
            'ethics_assessment': ethics_assessment is not None,
            'timestamp': datetime.now(timezone.utc)
        }

    async def _extract_metrics(self, interaction: AIInteraction) -> Dict[str, float]:
        """
        Extract metrics from interaction

        In real system, this would include:
        - Response accuracy checking
        - Hallucination detection
        - Citation verification
        - Sentiment analysis

        For MVP, we simulate with realistic values
        """
        # Simulate metrics with some variance
        base_values = {
            'response_accuracy': 0.93,
            'hallucination_rate': 0.06,
            'user_satisfaction': 4.2,
            'citation_accuracy': 0.97,
            'privacy_incidents': 0.0
        }

        # Add random variance
        metrics = {}
        for name, base in base_values.items():
            if name in ['response_accuracy', 'citation_accuracy', 'user_satisfaction']:
                variance = random.uniform(-0.1, 0.05)
            else:
                variance = random.uniform(-0.02, 0.05)

            value = base + variance
            # Clamp values
            if name == 'user_satisfaction':
                value = max(1.0, min(5.0, value))
            else:
                value = max(0.0, min(1.0, value))

            metrics[name] = value

        return metrics

    async def process_feedback(self, feedback: UserFeedback) -> Dict:
        """
        Process user feedback

        Args:
            feedback: User feedback to process

        Returns:
            Processing summary
        """
        # Simple sentiment analysis
        if feedback.comment:
            sentiment = self._analyze_sentiment(feedback.comment)
            feedback.sentiment = sentiment

        # Auto-categorize based on rating and comment
        categories = self._categorize_feedback(feedback)
        feedback.categories = categories

        # Store feedback
        storage.store_feedback(feedback)

        print(f"✓ Feedback processed: {feedback.feedback_id} (sentiment: {feedback.sentiment}, rating: {feedback.rating}/5)")

        return {
            'feedback_id': feedback.feedback_id,
            'sentiment': feedback.sentiment,
            'categories': categories,
            'requires_action': feedback.rating <= 2
        }

    def _analyze_sentiment(self, text: str) -> str:
        """
        Simple sentiment analysis

        In real system, would use NLP model (spaCy/Transformers)
        For MVP, use keyword matching
        """
        text_lower = text.lower()

        negative_keywords = ['bad', 'terrible', 'awful', 'poor', 'wrong', 'error', 'hate', 'disappointed']
        positive_keywords = ['good', 'great', 'excellent', 'amazing', 'perfect', 'love', 'helpful', 'accurate']

        negative_count = sum(1 for word in negative_keywords if word in text_lower)
        positive_count = sum(1 for word in positive_keywords if word in text_lower)

        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'

    def _categorize_feedback(self, feedback: UserFeedback) -> List[str]:
        """
        Categorize feedback

        In real system, would use ML classifier
        For MVP, use heuristics
        """
        categories = []

        if feedback.rating <= 2:
            categories.append('low_satisfaction')
        elif feedback.rating >= 4:
            categories.append('high_satisfaction')

        if feedback.comment:
            comment_lower = feedback.comment.lower()

            if any(word in comment_lower for word in ['wrong', 'incorrect', 'error', 'inaccurate']):
                categories.append('accuracy_issue')

            if any(word in comment_lower for word in ['slow', 'time', 'wait', 'performance']):
                categories.append('performance_issue')

            if any(word in comment_lower for word in ['bias', 'unfair', 'discriminat']):
                categories.append('bias_concern')

            if any(word in comment_lower for word in ['privacy', 'personal', 'data']):
                categories.append('privacy_concern')

        if not categories:
            categories.append('general')

        return categories

    def get_metrics_summary(self, hours: int = 24) -> Dict:
        """Get summary of recent metrics"""
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        summary = {}
        for metric_name, threshold in self.safety_provider.get_all_thresholds().items():
            metrics = storage.get_metrics(metric_name, start_time=start_time)

            if metrics:
                values = [m.value for m in metrics]
                avg_value = sum(values) / len(values)

                # Check status
                violation = self.safety_provider.check_threshold(metric_name, avg_value)
                status = '✗ ALERT' if violation else '✓ OK'

                summary[metric_name] = {
                    'average': avg_value,
                    'count': len(values),
                    'target': threshold.target,
                    'status': status,
                    'trend': self._calculate_trend(values)
                }

        return summary

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from values"""
        if len(values) < 2:
            return 'stable'

        # Compare first half vs second half
        mid = len(values) // 2
        first_half_avg = sum(values[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(values[mid:]) / (len(values) - mid)

        diff = second_half_avg - first_half_avg
        if abs(diff) < 0.01:
            return 'stable'
        elif diff > 0:
            return 'improving'
        else:
            return 'declining'

    def generate_report(self, days: int = 7) -> str:
        """Generate comprehensive monitoring report"""
        lines = [
            "\n" + "="*70,
            "POST-MARKET MONITORING REPORT",
            "="*70,
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Period: Last {days} days",
            ""
        ]

        # Interactions summary
        start_time = datetime.now(timezone.utc) - timedelta(days=days)
        interactions = storage.get_interactions(start_time=start_time)
        lines.append(f"INTERACTIONS: {len(interactions)} total")
        lines.append("-"*70)

        # Metrics summary
        lines.append("\nMETRICS SUMMARY:")
        lines.append("-"*70)
        metrics_summary = self.get_metrics_summary(hours=days*24)
        for metric_name, data in metrics_summary.items():
            lines.append(f"{data['status']} {metric_name}: {data['average']:.3f} "
                        f"(target: {data['target']:.3f}, trend: {data['trend']})")

        # Alerts
        active_alerts = storage.get_active_alerts()
        lines.append(f"\nACTIVE ALERTS: {len(active_alerts)}")
        lines.append("-"*70)
        for alert in active_alerts[-5:]:  # Show last 5
            lines.append(f"  [{alert.severity.value.upper()}] {alert.alert_type}: "
                        f"{alert.metric_name}={alert.current_value:.3f}")

        # Bias monitoring
        lines.append("\nBIAS MONITORING:")
        lines.append("-"*70)
        bias_report = self.ethics_bridge.get_bias_report()
        lines.append(bias_report)

        # Incidents
        incident_stats = self.incident_trigger.get_incident_stats()
        lines.append("\nINCIDENT STATISTICS:")
        lines.append("-"*70)
        lines.append(f"  Total: {incident_stats['total_incidents']}")
        lines.append(f"  Active: {incident_stats['active_incidents']}")
        lines.append(f"  Closed: {incident_stats['closed_incidents']}")

        # Feedback
        recent_feedback = storage.get_recent_feedback(days=days)
        lines.append(f"\nUSER FEEDBACK: {len(recent_feedback)} submissions")
        lines.append("-"*70)
        if recent_feedback:
            avg_rating = sum(f.rating for f in recent_feedback) / len(recent_feedback)
            sentiments = [f.sentiment for f in recent_feedback if f.sentiment]
            sentiment_dist = {
                'positive': sentiments.count('positive'),
                'neutral': sentiments.count('neutral'),
                'negative': sentiments.count('negative')
            }
            lines.append(f"  Average Rating: {avg_rating:.2f}/5")
            lines.append(f"  Sentiment: {sentiment_dist}")

        lines.append("\n" + "="*70)

        return "\n".join(lines)
