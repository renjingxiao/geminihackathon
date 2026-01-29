#!/usr/bin/env python3
"""
Human Oversight CLI - EU AI Act Article 14
Command-line interface for human oversight controls.

Usage:
    python human_oversight_cli.py submit --action "action" --desc "description"
    python human_oversight_cli.py queue
    python human_oversight_cli.py approve --id DEC-xxx --reviewer user_id
    python human_oversight_cli.py reject --id DEC-xxx --reviewer user_id --reason "reason"
    python human_oversight_cli.py override --id DEC-xxx --reviewer user_id --new-action "action"
    python human_oversight_cli.py explain --id DEC-xxx
    python human_oversight_cli.py report
    python human_oversight_cli.py demo
"""

import sys
import json
import argparse

from human_oversight import (
    HumanOversightSystem,
    RiskLevel,
    DecisionStatus
)


def cmd_submit(args):
    """Submit AI decision for human review"""
    system = HumanOversightSystem(ai_system_id=args.system_id)

    affected = args.affected.split(",") if args.affected else ["unknown"]

    decision = system.submit_decision(
        action=args.action,
        description=args.desc,
        confidence=args.confidence,
        affected_users=affected,
        reversible=not args.irreversible
    )

    print(f"\nDecision submitted for review:")
    print(f"  ID: {decision.decision_id}")
    print(f"  Action: {decision.action}")
    print(f"  Risk Level: {decision.risk_level.value}")
    print(f"  Status: {decision.status.value}")
    print(f"  Requires: {system.risk_thresholds[decision.risk_level]['consent'].value} consent")

    return 0


def cmd_queue(args):
    """List pending decisions"""
    system = HumanOversightSystem(ai_system_id=args.system_id)

    # Load from storage
    pending = system.get_pending_queue()

    if not pending:
        print("\nNo pending decisions.")
        return 0

    print(f"\nPending Decisions ({len(pending)}):")
    print("-" * 60)

    for d in pending:
        print(f"\n  ID: {d['decision_id']}")
        print(f"  Action: {d['action']}")
        print(f"  Risk: {d['risk_level'].upper()}")
        print(f"  Confidence: {d['confidence']*100:.1f}%")
        print(f"  Affected: {len(d['affected_users'])} users")

    return 0


def cmd_approve(args):
    """Approve a pending decision"""
    system = HumanOversightSystem(ai_system_id=args.system_id)

    success = system.approve_decision(args.id, args.reviewer)

    if success:
        print(f"\nDecision {args.id} APPROVED by {args.reviewer}")
    else:
        print(f"\nFailed to approve. Decision not found or already processed.")
        return 1

    return 0


def cmd_reject(args):
    """Reject a pending decision"""
    system = HumanOversightSystem(ai_system_id=args.system_id)

    success = system.reject_decision(args.id, args.reviewer, args.reason)

    if success:
        print(f"\nDecision {args.id} REJECTED by {args.reviewer}")
        print(f"Reason: {args.reason}")
    else:
        print(f"\nFailed to reject. Decision not found or already processed.")
        return 1

    return 0


def cmd_override(args):
    """Override a pending decision"""
    system = HumanOversightSystem(ai_system_id=args.system_id)

    override = system.override_decision(
        args.id,
        args.reviewer,
        args.new_action,
        args.reason or "Human override"
    )

    print(f"\nDecision {args.id} OVERRIDDEN")
    print(f"New Decision ID: {override.decision_id}")
    print(f"New Action: {override.action}")
    print(f"By: {args.reviewer}")

    return 0


def cmd_explain(args):
    """Get explanation for a decision"""
    system = HumanOversightSystem(ai_system_id=args.system_id, use_gemini=args.use_gemini)

    explanation = system.explain_decision(args.id)

    if "error" in explanation:
        print(f"\nError: {explanation['error']}")
        return 1

    print(f"\nDecision Explanation:")
    print("-" * 40)
    print(f"  ID: {explanation['decision_id']}")
    print(f"  What: {explanation['what']}")
    print(f"  Why: {explanation['why']}")
    print(f"  Confidence: {explanation['confidence']}")
    print(f"  Risk Level: {explanation['risk_level']}")
    print(f"  Reversible: {explanation['can_undo']}")
    print(f"  Status: {explanation['status']}")

    if explanation.get('detailed'):
        print(f"\nDetailed Explanation:")
        print(f"  {explanation['detailed']}")

    return 0


def cmd_report(args):
    """Generate oversight report"""
    system = HumanOversightSystem(ai_system_id=args.system_id)

    report = system.generate_oversight_report()

    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report saved to: {args.output}")
    else:
        print(report)

    return 0


def cmd_emergency(args):
    """Emergency stop all pending decisions"""
    system = HumanOversightSystem(ai_system_id=args.system_id)

    result = system.emergency_stop(args.reviewer, args.reason)

    print("\n" + "!" * 60)
    print("EMERGENCY STOP ACTIVATED")
    print("!" * 60)
    print(f"\nStopped {len(result['stopped_decisions'])} decisions")
    print(f"By: {result['reviewer']}")
    print(f"Reason: {result['reason']}")
    print(f"Time: {result['timestamp']}")

    return 0


def cmd_demo(args):
    """Run demo with sample scenarios"""
    print("=" * 60)
    print("EU AI Act Article 14 - Human Oversight Demo")
    print("=" * 60)

    system = HumanOversightSystem(ai_system_id="DEMO-001", use_gemini=args.use_gemini)

    # Scenario 1: Low-risk decision
    print("\n[1] LOW RISK: Sending notification email")
    print("-" * 40)
    d1 = system.submit_decision(
        action="send_notification",
        description="Send weekly newsletter to subscribed users",
        confidence=0.95,
        affected_users=["user_001"],
        reversible=True
    )
    print(f"Decision: {d1.decision_id}")
    print(f"Risk: {d1.risk_level.value}")
    print(f"Consent Required: {system.risk_thresholds[d1.risk_level]['consent'].value}")

    # Auto-approve low risk
    system.approve_decision(d1.decision_id, "auto_reviewer")
    print("Status: Auto-approved")

    # Scenario 2: Medium-risk decision
    print("\n[2] MEDIUM RISK: Updating user preferences")
    print("-" * 40)
    d2 = system.submit_decision(
        action="update_preferences",
        description="Update privacy settings based on AI recommendation",
        confidence=0.78,
        affected_users=["user_002", "user_003", "user_004"],
        reversible=True
    )
    print(f"Decision: {d2.decision_id}")
    print(f"Risk: {d2.risk_level.value}")
    print(f"Consent Required: {system.risk_thresholds[d2.risk_level]['consent'].value}")

    # Show options
    print("\nOverride Options:")
    for opt in system.get_override_options(d2.decision_id):
        print(f"  - {opt['action']}: {opt['description']}")

    # Human rejects
    system.reject_decision(d2.decision_id, "reviewer_001", "Need user confirmation first")
    print("\nStatus: Rejected by reviewer_001")

    # Scenario 3: High-risk decision
    print("\n[3] HIGH RISK: Account suspension")
    print("-" * 40)
    d3 = system.submit_decision(
        action="suspend_account",
        description="Suspend account due to suspicious activity",
        confidence=0.65,
        affected_users=["user_999"],
        reversible=False
    )
    print(f"Decision: {d3.decision_id}")
    print(f"Risk: {d3.risk_level.value}")
    print(f"Consent Required: {system.risk_thresholds[d3.risk_level]['consent'].value}")

    # Human overrides
    override = system.override_decision(
        d3.decision_id,
        "supervisor_001",
        "temporary_restriction",
        "Apply temporary restriction instead of full suspension"
    )
    print(f"\nStatus: Overridden")
    print(f"New Action: {override.action}")

    # Scenario 4: Get explanation
    print("\n[4] Decision Explanation")
    print("-" * 40)
    exp = system.explain_decision(override.decision_id)
    print(f"What: {exp['what']}")
    print(f"Confidence: {exp['confidence']}")
    print(f"Reviewed By: {exp['reviewed_by']}")

    # Generate report
    print("\n[5] Generating Report")
    print("-" * 40)
    report = system.generate_oversight_report()
    report_path = system.storage_dir / "demo_report.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"Report saved: {report_path}")

    print("\n" + "=" * 60)
    print("Demo complete.")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="EU AI Act Article 14 - Human Oversight CLI"
    )
    parser.add_argument(
        "--system-id",
        default="AI-SYSTEM-001",
        help="AI system identifier"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit decision for review")
    submit_parser.add_argument("--action", required=True, help="Action to perform")
    submit_parser.add_argument("--desc", required=True, help="Description")
    submit_parser.add_argument("--confidence", type=float, default=0.8, help="Confidence 0-1")
    submit_parser.add_argument("--affected", help="Comma-separated affected user IDs")
    submit_parser.add_argument("--irreversible", action="store_true", help="Mark as irreversible")

    # Queue command
    subparsers.add_parser("queue", help="List pending decisions")

    # Approve command
    approve_parser = subparsers.add_parser("approve", help="Approve decision")
    approve_parser.add_argument("--id", required=True, help="Decision ID")
    approve_parser.add_argument("--reviewer", required=True, help="Reviewer ID")

    # Reject command
    reject_parser = subparsers.add_parser("reject", help="Reject decision")
    reject_parser.add_argument("--id", required=True, help="Decision ID")
    reject_parser.add_argument("--reviewer", required=True, help="Reviewer ID")
    reject_parser.add_argument("--reason", required=True, help="Rejection reason")

    # Override command
    override_parser = subparsers.add_parser("override", help="Override decision")
    override_parser.add_argument("--id", required=True, help="Decision ID")
    override_parser.add_argument("--reviewer", required=True, help="Reviewer ID")
    override_parser.add_argument("--new-action", required=True, help="New action")
    override_parser.add_argument("--reason", help="Override reason")

    # Explain command
    explain_parser = subparsers.add_parser("explain", help="Explain decision")
    explain_parser.add_argument("--id", required=True, help="Decision ID")
    explain_parser.add_argument("--use-gemini", action="store_true", help="Use Gemini AI")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate oversight report")
    report_parser.add_argument("--output", help="Output file path")

    # Emergency command
    emergency_parser = subparsers.add_parser("emergency", help="Emergency stop")
    emergency_parser.add_argument("--reviewer", required=True, help="Reviewer ID")
    emergency_parser.add_argument("--reason", required=True, help="Emergency reason")

    # Demo command
    demo_parser = subparsers.add_parser("demo", help="Run demo scenarios")
    demo_parser.add_argument("--use-gemini", action="store_true", help="Use Gemini AI")

    args = parser.parse_args()

    commands = {
        "submit": cmd_submit,
        "queue": cmd_queue,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "override": cmd_override,
        "explain": cmd_explain,
        "report": cmd_report,
        "emergency": cmd_emergency,
        "demo": cmd_demo
    }

    if args.command in commands:
        return commands[args.command](args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
