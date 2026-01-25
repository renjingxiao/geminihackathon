"""
AI Auditor - Batch analysis of logs using Gemini LLM.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv

from utils import (
    get_recent_logs, RISK_CSV, OPERATIONAL_CSV, OUTPUT_DIR,
    FINAL_OUTPUT_DIR, REPORT_PATH
)

# Load environment variables
load_dotenv()

# Model configuration
PRIMARY_MODEL = "gemini-3-pro-preview"
FALLBACK_MODEL = "gemini-2.0-flash-exp"


def configure_genai():
    """Configure the Gemini API."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment")
    genai.configure(api_key=api_key)


def create_audit_prompt(risk_logs: list, operational_logs: list) -> str:
    """Create a prompt for the AI auditor."""
    risk_summary = "\n".join([
        f"- [{log.get('Risk Category (Art 79)', 'N/A')}] {log.get('Description of Event', 'N/A')}"
        for log in risk_logs[-20:]  # Last 20 risk entries
    ]) or "No risk events recorded."
    
    ops_count = len(operational_logs)
    
    prompt = f"""You are an AI compliance auditor analyzing logs for EU AI Act Article 12 compliance.

## Log Summary
- Total Operations Logged: {ops_count}
- Recent Risk/Incident Events:
{risk_summary}

## Task
1. Identify any recurring patterns in the risk events
2. Assess compliance with Article 12 logging requirements
3. Provide actionable recommendations

## Output Format
Generate a compliance report in Markdown format with sections:
- Executive Summary
- Risk Pattern Analysis
- Compliance Assessment
- Recommendations

Be concise and focus on actionable insights."""
    
    return prompt


def audit_logs(
    n_risk: int = 50,
    n_ops: int = 100
) -> str:
    """
    Run an AI audit on recent logs.
    Returns the path to the generated report.
    """
    configure_genai()
    
    # Get recent logs
    risk_logs = get_recent_logs(RISK_CSV, n_risk)
    ops_logs = get_recent_logs(OPERATIONAL_CSV, n_ops)
    
    # Create prompt
    prompt = create_audit_prompt(risk_logs, ops_logs)
    
    # Try primary model, fallback if needed
    report_content = None
    used_model = None
    
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            report_content = response.text
            used_model = model_name
            break
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            continue
    
    if not report_content:
        report_content = f"""# Compliance Audit Report

**Generated**: {datetime.now().isoformat()}
**Status**: FAILED - No model available

## Error
Unable to generate audit report. Both {PRIMARY_MODEL} and {FALLBACK_MODEL} failed.

## Manual Review Required
Please review the logs manually:
- Risk Logs: {RISK_CSV}
- Operational Logs: {OPERATIONAL_CSV}
"""
    else:
        # Add header to report
        report_content = f"""# AI Act Article 12 Compliance Audit Report

**Generated**: {datetime.now().isoformat()}
**Model Used**: {used_model}
**Risk Events Analyzed**: {len(risk_logs)}
**Operations Analyzed**: {len(ops_logs)}

---

{report_content}
"""
    
    # Save report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_content, encoding='utf-8')
    
    return str(REPORT_PATH)


def audit_logs_sync() -> str:
    """Synchronous wrapper for audit_logs."""
    return audit_logs()
