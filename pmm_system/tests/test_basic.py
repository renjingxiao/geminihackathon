"""
Basic tests for PMM system
"""
import pytest
from datetime import datetime, timezone

from pmm_agent.data.models import AIInteraction, UserFeedback, SafetyThreshold
from pmm_agent.integrations.safety_provider import SafetyMetricsProvider
from pmm_agent.integrations.ethics_bridge import EthicsMonitoringBridge


def test_safety_provider():
    """Test SafetyMetricsProvider"""
    provider = SafetyMetricsProvider()

    # Test threshold loading
    threshold = provider.get_threshold('response_accuracy')
    assert threshold is not None
    assert threshold.target == 0.95

    # Test threshold checking
    # Should trigger alert (below alert threshold)
    result = provider.check_threshold('response_accuracy', 0.88)
    assert result == 'alert'

    # Should trigger critical (below critical threshold)
    result = provider.check_threshold('response_accuracy', 0.82)
    assert result == 'critical'

    # Should be OK
    result = provider.check_threshold('response_accuracy', 0.96)
    assert result is None


def test_ethics_bridge():
    """Test EthicsMonitoringBridge"""
    bridge = EthicsMonitoringBridge()

    # Create test interaction
    interaction = AIInteraction(
        interaction_id="test_001",
        timestamp=datetime.now(timezone.utc),
        user_id="test_user",
        prompt="Test prompt",
        response="Test response",
        response_time=0.5,
        model_version="test",
        metadata={},
        demographics={'gender': 'female', 'age': '25-35'}
    )

    # Log interaction
    bridge.log_interaction(interaction)

    # Check alerts (should be none yet)
    alerts = bridge.check_bias_alerts()
    assert isinstance(alerts, list)


def test_ai_interaction_model():
    """Test AIInteraction model"""
    interaction = AIInteraction(
        interaction_id="test_001",
        timestamp=datetime.now(timezone.utc),
        user_id="test_user",
        prompt="What is AI?",
        response="AI is artificial intelligence",
        response_time=0.523,
        model_version="test-1.0",
        metadata={"temperature": 0.7}
    )

    assert interaction.interaction_id == "test_001"
    assert interaction.user_id == "test_user"
    assert interaction.response_time == 0.523


def test_user_feedback_model():
    """Test UserFeedback model"""
    feedback = UserFeedback(
        feedback_id="fb_001",
        interaction_id="int_001",
        user_id="user_001",
        timestamp=datetime.now(timezone.utc),
        rating=4,
        comment="Good response"
    )

    assert feedback.feedback_id == "fb_001"
    assert feedback.rating == 4
    assert feedback.comment == "Good response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
