#!/usr/bin/env python3
"""
Demo script for PMM System
Demonstrates all key features
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pmm_agent.core.pmm_core import PMMCoreAgent
from pmm_agent.data.models import AIInteraction, UserFeedback


async def run_demo():
    """Run comprehensive demo"""
    print("\n" + "="*70)
    print("POST-MARKET MONITORING SYSTEM - DEMO")
    print("="*70)
    print("\nThis demo shows:")
    print("1. AI interaction monitoring")
    print("2. Bias detection")
    print("3. Alert triggering")
    print("4. Incident creation")
    print("5. User feedback processing")
    print("6. Report generation")
    print("\n" + "="*70 + "\n")

    # Initialize PMM Agent
    print("Initializing PMM Agent...")
    pmm = PMMCoreAgent()
    print()

    # Demographics for bias testing
    demographics_options = [
        {'gender': 'male', 'age': '25-35', 'race': 'caucasian'},
        {'gender': 'female', 'age': '35-45', 'race': 'asian'},
        {'gender': 'male', 'age': '45-55', 'race': 'african_american'},
        {'gender': 'female', 'age': '25-35', 'race': 'hispanic'},
        None  # Some without demographics
    ]

    print("="*70)
    print("PHASE 1: Simulating 20 AI Interactions")
    print("="*70 + "\n")

    for i in range(20):
        interaction = AIInteraction(
            interaction_id=f"demo_int_{i+1:03d}",
            timestamp=datetime.now(timezone.utc),
            user_id=f"user_{i % 5 + 1}",
            prompt=f"What is the capital of {'France' if i % 2 else 'Germany'}?",
            response=f"The capital is {'Paris' if i % 2 else 'Berlin'}.",
            response_time=0.5 + (i % 5) * 0.1,
            model_version="gpt-4",
            metadata={'temperature': 0.7},
            demographics=demographics_options[i % len(demographics_options)]
        )

        print(f"Processing interaction {i+1}/20... ", end='')
        result = await pmm.process_interaction(interaction)
        print(f"✓ (alerts: {result['alerts_triggered']}, bias alerts: {result['bias_alerts']})")

        # Short delay for readability
        if (i + 1) % 5 == 0:
            print()
            await asyncio.sleep(0.2)

    print("\n" + "="*70)
    print("PHASE 2: Simulating User Feedback")
    print("="*70 + "\n")

    feedback_samples = [
        {
            "rating": 5,
            "comment": "Excellent response, very accurate and helpful!",
            "issues": []
        },
        {
            "rating": 4,
            "comment": "Good answer but could be more detailed.",
            "issues": []
        },
        {
            "rating": 2,
            "comment": "The response was wrong and misleading.",
            "issues": ["accuracy_issue"]
        },
        {
            "rating": 1,
            "comment": "Terrible answer, completely incorrect and showed bias.",
            "issues": ["accuracy_issue", "bias_concern"]
        },
        {
            "rating": 3,
            "comment": "Response was slow but correct.",
            "issues": ["performance_issue"]
        }
    ]

    for i, fb_data in enumerate(feedback_samples):
        feedback = UserFeedback(
            feedback_id=f"demo_fb_{i+1:03d}",
            interaction_id=f"demo_int_{i+1:03d}",
            user_id=f"user_{i+1}",
            timestamp=datetime.now(timezone.utc),
            rating=fb_data["rating"],
            comment=fb_data["comment"],
            issues=fb_data["issues"]
        )

        result = await pmm.process_feedback(feedback)
        print(f"✓ Feedback {i+1}: Rating {fb_data['rating']}/5, "
              f"Sentiment: {result['sentiment']}, "
              f"Action Needed: {result['requires_action']}")

    print("\n" + "="*70)
    print("PHASE 3: Generating Reports")
    print("="*70 + "\n")

    # Metrics summary
    print("📊 Metrics Summary (Last 24 hours):")
    print("-"*70)
    metrics_summary = pmm.get_metrics_summary(hours=24)
    for metric_name, data in metrics_summary.items():
        print(f"{data['status']} {metric_name}: {data['average']:.3f} "
              f"(target: {data['target']:.3f}, trend: {data['trend']})")

    print()

    # Bias report
    print("👥 Bias Monitoring Report:")
    print("-"*70)
    bias_report = pmm.ethics_bridge.get_bias_report()
    print(bias_report)
    print()

    # Incident statistics
    print("🚨 Incident Statistics:")
    print("-"*70)
    incident_stats = pmm.incident_trigger.get_incident_stats()
    print(f"  Total Incidents: {incident_stats['total_incidents']}")
    print(f"  Active: {incident_stats['active_incidents']}")
    print(f"  Closed: {incident_stats['closed_incidents']}")
    print()

    # Full report
    print("="*70)
    print("COMPREHENSIVE REPORT")
    print("="*70)
    full_report = pmm.generate_report(days=1)
    print(full_report)

    print("\n" + "="*70)
    print("DEMO COMPLETED SUCCESSFULLY")
    print("="*70)
    print("\nNext steps:")
    print("1. Start the API server: python -m pmm_agent.main")
    print("2. Visit http://localhost:8000/docs for API documentation")
    print("3. Try the test client: python scripts/test_client.py")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
