#!/usr/bin/env python3
"""
EU AI Act Article 14 - Human Oversight
Enhanced controls for human oversight of AI systems.

Features:
- Explicit consent mechanism
- Enhanced verification steps
- Clear override controls
- System understanding aids
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime
from pathlib import Path
import json
import os
import hashlib
import uuid


# ============================================================
# Enums and Constants
# ============================================================
class RiskLevel(Enum):
    """Risk levels for AI decisions"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionStatus(Enum):
    """Status of AI decision"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    OVERRIDDEN = "overridden"
    EXPIRED = "expired"


class ConsentType(Enum):
    """Types of consent"""
    IMPLICIT = "implicit"        # Low risk, proceed unless objected
    EXPLICIT = "explicit"        # Requires active confirmation
    VERIFIED = "verified"        # Multi-step verification required
    WITNESSED = "witnessed"      # Requires third-party witness


# ============================================================
# Data Models
# ============================================================
@dataclass
class ConsentRecord:
    """Record of user consent"""
    consent_id: str
    user_id: str
    action_type: str
    consent_type: ConsentType
    granted: bool
    timestamp: datetime
    expiry: Optional[datetime]
    verification_method: str
    metadata: Dict = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if consent is still valid"""
        if not self.granted:
            return False
        if self.expiry and datetime.now() > self.expiry:
            return False
        return True

    def to_dict(self) -> Dict:
        return {
            "consent_id": self.consent_id,
            "user_id": self.user_id,
            "action_type": self.action_type,
            "consent_type": self.consent_type.value,
            "granted": self.granted,
            "timestamp": self.timestamp.isoformat(),
            "expiry": self.expiry.isoformat() if self.expiry else None,
            "verification_method": self.verification_method,
            "metadata": self.metadata
        }


@dataclass
class AIDecision:
    """Represents an AI system decision requiring oversight"""
    decision_id: str
    ai_system_id: str
    action: str
    description: str
    risk_level: RiskLevel
    status: DecisionStatus
    created_at: datetime
    confidence: float
    explanation: str
    affected_users: List[str]
    reversible: bool
    human_reviewer: Optional[str] = None
    review_timestamp: Optional[datetime] = None
    override_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "decision_id": self.decision_id,
            "ai_system_id": self.ai_system_id,
            "action": self.action,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "confidence": self.confidence,
            "explanation": self.explanation,
            "affected_users": self.affected_users,
            "reversible": self.reversible,
            "human_reviewer": self.human_reviewer,
            "review_timestamp": self.review_timestamp.isoformat() if self.review_timestamp else None,
            "override_reason": self.override_reason
        }


@dataclass
class SystemExplanation:
    """AI system explanation for user understanding"""
    component: str
    purpose: str
    data_used: List[str]
    decision_factors: List[str]
    limitations: List[str]
    confidence_meaning: str
    how_to_override: str


# ============================================================
# Human Oversight System
# ============================================================
class HumanOversightSystem:
    """
    EU AI Act Article 14 Compliance
    Human Oversight Control System
    """

    def __init__(self, ai_system_id: str, use_gemini: bool = True):
        self.ai_system_id = ai_system_id
        self.use_gemini = use_gemini
        self.consent_records: List[ConsentRecord] = []
        self.pending_decisions: List[AIDecision] = []
        self.decision_history: List[AIDecision] = []

        # Storage
        self.storage_dir = Path(__file__).parent / "oversight_records"
        self.storage_dir.mkdir(exist_ok=True)

        # Risk thresholds
        self.risk_thresholds = {
            RiskLevel.LOW: {"consent": ConsentType.IMPLICIT, "timeout_hours": 24},
            RiskLevel.MEDIUM: {"consent": ConsentType.EXPLICIT, "timeout_hours": 4},
            RiskLevel.HIGH: {"consent": ConsentType.VERIFIED, "timeout_hours": 1},
            RiskLevel.CRITICAL: {"consent": ConsentType.WITNESSED, "timeout_hours": 0}
        }

        # Load existing data from files
        self._load_from_storage()

    # ========================================================
    # 1. Consent Mechanism
    # ========================================================
    def request_consent(
        self,
        user_id: str,
        action_type: str,
        risk_level: RiskLevel,
        description: str
    ) -> ConsentRecord:
        """
        Request explicit consent from user for an AI action.
        Returns consent record (may be pending verification).
        """
        consent_type = self.risk_thresholds[risk_level]["consent"]
        timeout = self.risk_thresholds[risk_level]["timeout_hours"]

        consent = ConsentRecord(
            consent_id=self._generate_id("CON"),
            user_id=user_id,
            action_type=action_type,
            consent_type=consent_type,
            granted=False,  # Pending until verified
            timestamp=datetime.now(),
            expiry=datetime.now() if timeout == 0 else None,
            verification_method=self._get_verification_method(consent_type),
            metadata={
                "risk_level": risk_level.value,
                "description": description,
                "ai_system": self.ai_system_id
            }
        )

        self.consent_records.append(consent)
        return consent

    def verify_consent(
        self,
        consent_id: str,
        verification_code: Optional[str] = None,
        witness_id: Optional[str] = None
    ) -> bool:
        """
        Verify and grant consent after user confirmation.
        """
        consent = self._find_consent(consent_id)
        if not consent:
            return False

        # Verify based on consent type
        if consent.consent_type == ConsentType.IMPLICIT:
            consent.granted = True
        elif consent.consent_type == ConsentType.EXPLICIT:
            consent.granted = True  # User clicked confirm
        elif consent.consent_type == ConsentType.VERIFIED:
            if verification_code and self._verify_code(consent_id, verification_code):
                consent.granted = True
        elif consent.consent_type == ConsentType.WITNESSED:
            if witness_id and self._verify_witness(witness_id):
                consent.granted = True
                consent.metadata["witness_id"] = witness_id

        if consent.granted:
            self._save_consent(consent)

        return consent.granted

    def revoke_consent(self, consent_id: str, reason: str = "") -> bool:
        """Revoke previously granted consent"""
        consent = self._find_consent(consent_id)
        if consent:
            consent.granted = False
            consent.metadata["revoked"] = True
            consent.metadata["revoke_reason"] = reason
            consent.metadata["revoke_time"] = datetime.now().isoformat()
            self._save_consent(consent)
            return True
        return False

    def _get_verification_method(self, consent_type: ConsentType) -> str:
        """Get verification method for consent type"""
        methods = {
            ConsentType.IMPLICIT: "auto_approve",
            ConsentType.EXPLICIT: "button_click",
            ConsentType.VERIFIED: "two_factor_code",
            ConsentType.WITNESSED: "witness_signature"
        }
        return methods.get(consent_type, "unknown")

    def _verify_code(self, consent_id: str, code: str) -> bool:
        """Verify 2FA code (simplified)"""
        expected = hashlib.sha256(consent_id.encode()).hexdigest()[:6].upper()
        return code.upper() == expected

    def _verify_witness(self, witness_id: str) -> bool:
        """Verify witness exists (simplified)"""
        return len(witness_id) > 0

    # ========================================================
    # 2. AI Decision Queue
    # ========================================================
    def submit_decision(
        self,
        action: str,
        description: str,
        confidence: float,
        affected_users: List[str],
        reversible: bool = True
    ) -> AIDecision:
        """
        Submit an AI decision for human review.
        Risk level is auto-assessed based on impact.
        """
        risk_level = self._assess_risk(confidence, affected_users, reversible)

        decision = AIDecision(
            decision_id=self._generate_id("DEC"),
            ai_system_id=self.ai_system_id,
            action=action,
            description=description,
            risk_level=risk_level,
            status=DecisionStatus.PENDING,
            created_at=datetime.now(),
            confidence=confidence,
            explanation=self._generate_explanation(action, confidence),
            affected_users=affected_users,
            reversible=reversible
        )

        self.pending_decisions.append(decision)
        self._save_decision(decision)

        return decision

    def approve_decision(
        self,
        decision_id: str,
        reviewer_id: str
    ) -> bool:
        """Human approves AI decision"""
        decision = self._find_decision(decision_id)
        if not decision or decision.status != DecisionStatus.PENDING:
            return False

        decision.status = DecisionStatus.APPROVED
        decision.human_reviewer = reviewer_id
        decision.review_timestamp = datetime.now()

        self._move_to_history(decision)
        self._save_decision(decision)
        return True

    def reject_decision(
        self,
        decision_id: str,
        reviewer_id: str,
        reason: str
    ) -> bool:
        """Human rejects AI decision"""
        decision = self._find_decision(decision_id)
        if not decision or decision.status != DecisionStatus.PENDING:
            return False

        decision.status = DecisionStatus.REJECTED
        decision.human_reviewer = reviewer_id
        decision.review_timestamp = datetime.now()
        decision.override_reason = reason

        self._move_to_history(decision)
        self._save_decision(decision)
        return True

    def override_decision(
        self,
        decision_id: str,
        reviewer_id: str,
        new_action: str,
        reason: str
    ) -> AIDecision:
        """Human overrides AI decision with alternative"""
        decision = self._find_decision(decision_id)
        if decision:
            decision.status = DecisionStatus.OVERRIDDEN
            decision.human_reviewer = reviewer_id
            decision.review_timestamp = datetime.now()
            decision.override_reason = reason
            self._move_to_history(decision)

        # Create new human decision
        override = AIDecision(
            decision_id=self._generate_id("OVR"),
            ai_system_id="HUMAN",
            action=new_action,
            description=f"Human override of {decision_id}: {reason}",
            risk_level=RiskLevel.LOW,
            status=DecisionStatus.APPROVED,
            created_at=datetime.now(),
            confidence=1.0,
            explanation="Human override decision",
            affected_users=decision.affected_users if decision else [],
            reversible=True,
            human_reviewer=reviewer_id,
            review_timestamp=datetime.now()
        )

        self.decision_history.append(override)
        self._save_decision(override)
        return override

    def _assess_risk(
        self,
        confidence: float,
        affected_users: List[str],
        reversible: bool
    ) -> RiskLevel:
        """Assess risk level of decision"""
        score = 0

        # Low confidence = higher risk
        if confidence < 0.5:
            score += 3
        elif confidence < 0.7:
            score += 2
        elif confidence < 0.9:
            score += 1

        # More affected users = higher risk
        if len(affected_users) > 100:
            score += 3
        elif len(affected_users) > 10:
            score += 2
        elif len(affected_users) > 1:
            score += 1

        # Irreversible = higher risk
        if not reversible:
            score += 2

        if score >= 6:
            return RiskLevel.CRITICAL
        elif score >= 4:
            return RiskLevel.HIGH
        elif score >= 2:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    # ========================================================
    # 3. System Understanding Aids
    # ========================================================
    def explain_system(self) -> SystemExplanation:
        """Generate human-readable system explanation"""
        return SystemExplanation(
            component=self.ai_system_id,
            purpose="This AI system assists with automated decision-making.",
            data_used=[
                "User input data",
                "Historical patterns",
                "Configured rules"
            ],
            decision_factors=[
                "Confidence score (0-100%)",
                "Risk assessment",
                "Affected user count",
                "Reversibility"
            ],
            limitations=[
                "Cannot guarantee 100% accuracy",
                "May not account for edge cases",
                "Requires human review for high-risk decisions"
            ],
            confidence_meaning=(
                "Confidence indicates the AI's certainty. "
                "90%+ = High certainty, 70-90% = Moderate, <70% = Low certainty."
            ),
            how_to_override=(
                "Use override_decision() with your reviewer ID, "
                "the alternative action, and your reasoning."
            )
        )

    def explain_decision(self, decision_id: str) -> Dict:
        """Generate explanation for specific decision"""
        decision = self._find_decision(decision_id)
        if not decision:
            decision = self._find_in_history(decision_id)
        if not decision:
            return {"error": "Decision not found"}

        explanation = {
            "decision_id": decision.decision_id,
            "what": decision.action,
            "why": decision.explanation,
            "confidence": f"{decision.confidence * 100:.1f}%",
            "risk_level": decision.risk_level.value,
            "who_affected": decision.affected_users,
            "can_undo": decision.reversible,
            "status": decision.status.value,
            "reviewed_by": decision.human_reviewer
        }

        if self.use_gemini:
            explanation["detailed"] = self._get_gemini_explanation(decision)

        return explanation

    def _generate_explanation(self, action: str, confidence: float) -> str:
        """Generate basic explanation for decision"""
        certainty = "high" if confidence > 0.9 else "moderate" if confidence > 0.7 else "low"
        return f"AI recommends '{action}' with {certainty} certainty ({confidence*100:.1f}%)."

    def _get_gemini_explanation(self, decision: AIDecision) -> str:
        """Get enhanced explanation from Gemini"""
        try:
            from google import genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return ""

            client = genai.Client(api_key=api_key)
            prompt = f"""Explain this AI decision in simple terms for a non-technical user:

Action: {decision.action}
Description: {decision.description}
Confidence: {decision.confidence * 100:.1f}%
Risk Level: {decision.risk_level.value}
Affected Users: {len(decision.affected_users)}
Reversible: {decision.reversible}

Provide a brief, clear explanation (2-3 sentences) that helps the user understand:
1. What the AI wants to do
2. Why it might be risky or safe
3. What happens if they approve or reject"""

            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt
            )
            return response.text.strip()
        except Exception:
            return ""

    # ========================================================
    # 4. Override Controls
    # ========================================================
    def get_override_options(self, decision_id: str) -> List[Dict]:
        """Get available override options for a decision"""
        decision = self._find_decision(decision_id)
        if not decision:
            return []

        options = [
            {
                "action": "approve",
                "description": "Accept the AI recommendation as-is",
                "requires": "reviewer_id"
            },
            {
                "action": "reject",
                "description": "Reject the AI recommendation completely",
                "requires": "reviewer_id, reason"
            },
            {
                "action": "override",
                "description": "Replace with your own decision",
                "requires": "reviewer_id, new_action, reason"
            },
            {
                "action": "defer",
                "description": "Request additional review",
                "requires": "reviewer_id, escalate_to"
            }
        ]

        # Add risk-specific options
        if decision.risk_level == RiskLevel.CRITICAL:
            options.append({
                "action": "emergency_stop",
                "description": "Halt all related AI operations immediately",
                "requires": "reviewer_id, authorization_code"
            })

        return options

    def emergency_stop(self, reviewer_id: str, reason: str) -> Dict:
        """Emergency stop all pending decisions"""
        stopped = []
        for decision in self.pending_decisions:
            decision.status = DecisionStatus.REJECTED
            decision.human_reviewer = reviewer_id
            decision.review_timestamp = datetime.now()
            decision.override_reason = f"EMERGENCY STOP: {reason}"
            stopped.append(decision.decision_id)
            self._save_decision(decision)

        self.decision_history.extend(self.pending_decisions)
        self.pending_decisions = []

        return {
            "action": "emergency_stop",
            "stopped_decisions": stopped,
            "reviewer": reviewer_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }

    # ========================================================
    # 5. Audit and Reporting
    # ========================================================
    def get_pending_queue(self) -> List[Dict]:
        """Get all pending decisions requiring review"""
        return [d.to_dict() for d in self.pending_decisions]

    def get_audit_log(self, limit: int = 50) -> List[Dict]:
        """Get recent decision history"""
        recent = sorted(
            self.decision_history,
            key=lambda x: x.created_at,
            reverse=True
        )[:limit]
        return [d.to_dict() for d in recent]

    def generate_oversight_report(self) -> str:
        """Generate compliance report for human oversight"""
        total_decisions = len(self.decision_history)
        approved = sum(1 for d in self.decision_history if d.status == DecisionStatus.APPROVED)
        rejected = sum(1 for d in self.decision_history if d.status == DecisionStatus.REJECTED)
        overridden = sum(1 for d in self.decision_history if d.status == DecisionStatus.OVERRIDDEN)

        report = f"""# Human Oversight Report
## AI System: {self.ai_system_id}
## Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
## Compliance: EU AI Act Article 14

---

### Executive Summary

| Metric | Value |
|--------|-------|
| Total Decisions Reviewed | {total_decisions} |
| Approved | {approved} |
| Rejected | {rejected} |
| Overridden | {overridden} |
| Pending Review | {len(self.pending_decisions)} |
| Active Consents | {sum(1 for c in self.consent_records if c.is_valid())} |

---

### Risk Distribution

"""
        # Count by risk level
        for level in RiskLevel:
            count = sum(1 for d in self.decision_history if d.risk_level == level)
            report += f"- **{level.value.upper()}**: {count}\n"

        report += "\n---\n\n### Recent Overrides\n\n"

        overrides = [d for d in self.decision_history if d.status == DecisionStatus.OVERRIDDEN][-5:]
        for d in overrides:
            report += f"- **{d.decision_id}**: {d.override_reason}\n"

        report += "\n---\n\n### Compliance Notes\n\n"
        report += "- All high-risk decisions require human approval before execution\n"
        report += "- Override capability is available for all AI decisions\n"
        report += "- Audit trail maintained for all human interventions\n"
        report += "- Emergency stop capability is active\n"

        return report

    # ========================================================
    # Helper Methods
    # ========================================================
    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID with prefix + timestamp + random suffix"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = uuid.uuid4().hex[:6]
        return f"{prefix}-{timestamp}-{random_suffix}"

    def _find_consent(self, consent_id: str) -> Optional[ConsentRecord]:
        for c in self.consent_records:
            if c.consent_id == consent_id:
                return c
        return None

    def _find_decision(self, decision_id: str) -> Optional[AIDecision]:
        for d in self.pending_decisions:
            if d.decision_id == decision_id:
                return d
        return None

    def _find_in_history(self, decision_id: str) -> Optional[AIDecision]:
        for d in self.decision_history:
            if d.decision_id == decision_id:
                return d
        return None

    def _move_to_history(self, decision: AIDecision):
        if decision in self.pending_decisions:
            self.pending_decisions.remove(decision)
        if decision not in self.decision_history:
            self.decision_history.append(decision)

    def _save_consent(self, consent: ConsentRecord):
        filepath = self.storage_dir / f"{consent.consent_id}.json"
        with open(filepath, 'w') as f:
            json.dump(consent.to_dict(), f, indent=2)

    def _save_decision(self, decision: AIDecision):
        filepath = self.storage_dir / f"{decision.decision_id}.json"
        with open(filepath, 'w') as f:
            json.dump(decision.to_dict(), f, indent=2)

    def _load_from_storage(self):
        """Load decisions from JSON files"""
        for filepath in self.storage_dir.glob("DEC-*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                decision = self._dict_to_decision(data)
                if decision.status == DecisionStatus.PENDING:
                    self.pending_decisions.append(decision)
                else:
                    self.decision_history.append(decision)
            except Exception:
                continue  # Skip corrupted files

        for filepath in self.storage_dir.glob("OVR-*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                decision = self._dict_to_decision(data)
                self.decision_history.append(decision)
            except Exception:
                continue

    def _dict_to_decision(self, data: Dict) -> AIDecision:
        """Convert dict from JSON to AIDecision object"""
        return AIDecision(
            decision_id=data["decision_id"],
            ai_system_id=data["ai_system_id"],
            action=data["action"],
            description=data["description"],
            risk_level=RiskLevel(data["risk_level"]),
            status=DecisionStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            confidence=data["confidence"],
            explanation=data["explanation"],
            affected_users=data["affected_users"],
            reversible=data["reversible"],
            human_reviewer=data.get("human_reviewer"),
            review_timestamp=datetime.fromisoformat(data["review_timestamp"]) if data.get("review_timestamp") else None,
            override_reason=data.get("override_reason")
        )


# ============================================================
# Main Entry Point
# ============================================================
def main():
    """Demo usage of HumanOversightSystem"""
    print("=" * 60)
    print("EU AI Act Article 14 - Human Oversight System")
    print("=" * 60)

    system = HumanOversightSystem(ai_system_id="DEMO-AI-001")

    # Demo 1: Submit decision for review
    print("\n[1] Submitting AI decision for human review...")
    decision = system.submit_decision(
        action="approve_loan",
        description="Approve loan application #12345 for $50,000",
        confidence=0.85,
        affected_users=["user_12345"],
        reversible=True
    )
    print(f"Decision ID: {decision.decision_id}")
    print(f"Risk Level: {decision.risk_level.value}")
    print(f"Status: {decision.status.value}")

    # Demo 2: Get explanation
    print("\n[2] Getting decision explanation...")
    explanation = system.explain_decision(decision.decision_id)
    print(f"What: {explanation['what']}")
    print(f"Confidence: {explanation['confidence']}")
    print(f"Risk: {explanation['risk_level']}")

    # Demo 3: Show override options
    print("\n[3] Available override options:")
    options = system.get_override_options(decision.decision_id)
    for opt in options:
        print(f"  - {opt['action']}: {opt['description']}")

    # Demo 4: Approve decision
    print("\n[4] Human approving decision...")
    system.approve_decision(decision.decision_id, "reviewer_001")
    print(f"Decision approved by reviewer_001")

    # Demo 5: Submit high-risk decision
    print("\n[5] Submitting HIGH risk decision...")
    high_risk = system.submit_decision(
        action="delete_user_data",
        description="Permanently delete user account and all data",
        confidence=0.6,
        affected_users=["user_999"],
        reversible=False
    )
    print(f"Decision ID: {high_risk.decision_id}")
    print(f"Risk Level: {high_risk.risk_level.value}")

    # Demo 6: Override decision
    print("\n[6] Human overriding decision...")
    override = system.override_decision(
        high_risk.decision_id,
        "supervisor_001",
        "archive_user_data",
        "Archive instead of delete for data retention compliance"
    )
    print(f"Override ID: {override.decision_id}")
    print(f"New Action: {override.action}")

    # Demo 7: Generate report
    print("\n[7] Generating oversight report...")
    report = system.generate_oversight_report()
    report_path = system.storage_dir / "oversight_report.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"Report saved: {report_path}")

    print("\n" + "=" * 60)
    print("Demo complete.")


if __name__ == "__main__":
    main()
