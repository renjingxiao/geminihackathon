"""
Integration with ai-ethics-advisor skill
Simplified bias monitoring bridge
"""
from collections import defaultdict
from typing import Dict, List, Optional
from datetime import datetime, timezone

from ..data.models import AIInteraction


class SimpleBiasMonitor:
    """
    Simplified bias monitor for MVP
    Based on: skills/health-safety/ai-ethics-advisor/modules/technical-safeguards/bias-monitoring.py
    """

    def __init__(self,
                 protected_attributes: List[str],
                 alert_thresholds: Dict[str, float],
                 window_size: int = 1000):
        self.protected_attributes = protected_attributes
        self.alert_thresholds = alert_thresholds
        self.window_size = window_size

        # Rolling windows per attribute
        self.predictions = defaultdict(list)
        self.attribute_values = defaultdict(lambda: defaultdict(list))

    def log_prediction(self,
                      prediction: int,
                      attributes: Dict[str, str]):
        """Log a single prediction for monitoring"""
        for attr in self.protected_attributes:
            if attr in attributes:
                key = attr
                self.predictions[key].append(prediction)
                self.attribute_values[key][attributes[attr]].append(
                    len(self.predictions[key]) - 1
                )

                # Maintain window size
                if len(self.predictions[key]) > self.window_size:
                    self._trim_window(key)

    def _trim_window(self, attr: str):
        """Remove oldest entries to maintain window size"""
        excess = len(self.predictions[attr]) - self.window_size
        self.predictions[attr] = self.predictions[attr][excess:]

        # Update indices
        for group in self.attribute_values[attr]:
            self.attribute_values[attr][group] = [
                i - excess for i in self.attribute_values[attr][group]
                if i >= excess
            ]

    def check_alerts(self) -> List[Dict]:
        """Check all thresholds and return any alerts"""
        alerts = []

        for attr in self.protected_attributes:
            if attr not in self.predictions or not self.predictions[attr]:
                continue

            metrics = self._compute_current_metrics(attr)

            if not metrics or 'selection_rates' not in metrics:
                continue

            # Check 4/5ths rule
            selection_rates = metrics['selection_rates']
            if len(selection_rates) < 2:
                continue

            max_rate = max(selection_rates.values()) if selection_rates else 0
            threshold = 0.8 * max_rate

            for group, rate in selection_rates.items():
                if rate < threshold:
                    alerts.append({
                        'type': 'demographic_parity',
                        'attribute': attr,
                        'group': group,
                        'value': rate,
                        'threshold': threshold,
                        'message': f"Selection rate for {group} in {attr} violates 4/5ths rule",
                        'severity': 'high' if rate < 0.6 * max_rate else 'medium'
                    })

        return alerts

    def _compute_current_metrics(self, attribute: str) -> Dict:
        """Compute current fairness metrics for an attribute"""
        if attribute not in self.predictions:
            return {}

        preds = self.predictions[attribute]
        if not preds:
            return {}

        metrics = {'selection_rates': {}}

        for group, indices in self.attribute_values[attribute].items():
            if indices:
                group_preds = [preds[i] for i in indices if i < len(preds)]
                if group_preds:
                    metrics['selection_rates'][group] = sum(group_preds) / len(group_preds)

        return metrics

    def get_summary_report(self) -> str:
        """Generate a summary report"""
        lines = ["=" * 60, "BIAS MONITORING REPORT", "=" * 60, ""]

        for attr in self.protected_attributes:
            metrics = self._compute_current_metrics(attr)
            if not metrics:
                continue

            lines.append(f"Attribute: {attr}")
            lines.append("-" * 40)

            if 'selection_rates' in metrics:
                lines.append("Selection Rates:")
                for group, rate in metrics['selection_rates'].items():
                    lines.append(f"  {group}: {rate:.3f}")

                # Check 4/5ths
                if len(metrics['selection_rates']) >= 2:
                    max_rate = max(metrics['selection_rates'].values())
                    threshold = 0.8 * max_rate
                    failing = [g for g, r in metrics['selection_rates'].items() if r < threshold]
                    if failing:
                        lines.append(f"  ⚠️ 4/5ths rule violated for: {', '.join(failing)}")
                    else:
                        lines.append("  ✓ All groups pass 4/5ths rule")

            lines.append("")

        alerts = self.check_alerts()
        if alerts:
            lines.append("ACTIVE ALERTS:")
            lines.append("-" * 40)
            for alert in alerts:
                lines.append(f"⚠️ {alert['message']}")
        else:
            lines.append("✓ No active alerts")

        return "\n".join(lines)


class EthicsMonitoringBridge:
    """
    Bridge to ai-ethics-advisor

    Integrates bias monitoring and ethics assessment
    """

    def __init__(self, protected_attributes: List[str] = None):
        if protected_attributes is None:
            protected_attributes = ['gender', 'race', 'age']

        self.bias_monitor = SimpleBiasMonitor(
            protected_attributes=protected_attributes,
            alert_thresholds={
                'demographic_parity': 0.8,
                'tpr_disparity': 0.05,
                'fpr_disparity': 0.05
            },
            window_size=1000
        )

        self.alert_history = []

    def log_interaction(self, interaction: AIInteraction):
        """
        Log interaction for bias monitoring

        Args:
            interaction: AI interaction record
        """
        if not interaction.demographics:
            return

        # Assume non-empty response is a positive prediction
        prediction = 1 if interaction.response else 0

        self.bias_monitor.log_prediction(
            prediction=prediction,
            attributes=interaction.demographics
        )

    def check_bias_alerts(self) -> List[Dict]:
        """Check for bias alerts"""
        alerts = self.bias_monitor.check_alerts()

        # Record alert history
        for alert in alerts:
            alert['detected_at'] = datetime.now(timezone.utc)
            self.alert_history.append(alert)

        return alerts

    def get_bias_report(self) -> str:
        """Get bias monitoring report"""
        return self.bias_monitor.get_summary_report()

    def should_trigger_ethics_assessment(self, alerts: List[Dict]) -> bool:
        """
        Determine if full ethics assessment should be triggered

        Based on ai-ethics-advisor/SKILL.md:
        - Tier 1: Rapid Screen - for minor issues
        - Tier 2: Comprehensive Assessment - for serious issues
        """
        if not alerts:
            return False

        # Trigger if any critical severity
        for alert in alerts:
            if alert.get('severity') == 'high':
                return True

        # Trigger if multiple groups affected
        affected_groups = set()
        for alert in alerts:
            if 'group' in alert:
                affected_groups.add(alert['group'])

        return len(affected_groups) >= 2

    async def trigger_ethics_assessment(self, alerts: List[Dict]) -> Dict:
        """
        Trigger ethics assessment

        In a real system, this would call ai-ethics-advisor's API
        For MVP, we return a simulated response
        """
        severity_count = sum(1 for a in alerts if a.get('severity') == 'high')

        if severity_count > 0:
            assessment_tier = 'tier2_comprehensive'
            recommendation = "Immediate review of model training data and bias mitigation required"
        else:
            assessment_tier = 'tier1_rapid'
            recommendation = "Monitor closely and review in next evaluation cycle"

        return {
            'assessment_tier': assessment_tier,
            'triggered_at': datetime.now(timezone.utc),
            'alerts_count': len(alerts),
            'high_severity_count': severity_count,
            'recommendation': recommendation,
            'action_required': severity_count > 0,
            'assessment_status': 'completed'
        }
