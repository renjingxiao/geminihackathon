---
name: automatic-logging
description: EU AI Act Article 12 automatic logging and compliance auditing. Use when user needs to log AI operations, monitor anomalies (latency >5s, DOS), generate compliance reports via Gemini LLM, or create Article 12 Excel workbooks.
---

# Automatic Logging

## Scripts

Run from `scripts/` directory:

| Script | Command | Output |
|--------|---------|--------|
| `logger.py` | Import and use decorator/class | Logs to CSV |
| `watchdog.py` | Auto-triggered by logger | Risk alerts |
| `auditor.py` | `python -c "from auditor import audit_logs; audit_logs()"` | `Output/Record_Keeping_Logging_Art12_Report.md` |
| `utils.py` | `python -c "from utils import consolidate_to_excel; consolidate_to_excel()"` | `Output/Record_Keeping_Logging_Art12.xlsx` |
| `seed_data.py` | `python seed_data.py` | Mock data in CSVs |

## Audit Prompt

```text
You are an AI compliance auditor analyzing logs for EU AI Act Article 12 compliance.

## Log Summary
- Total Operations Logged: {ops_count}
- Recent Risk/Incident Events:
{risk_summary}

## Task
1. Identify recurring patterns in risk events
2. Assess compliance with Article 12 requirements
3. Provide actionable recommendations

## Output Format
Markdown: Executive Summary, Risk Pattern Analysis, Compliance Assessment, Recommendations
```

## Example Data

Test data in `examples/`:

- `operational_logs.csv` - Sample operations
- `risk_logs.csv` - Sample risk events
- `capability_checklist.csv` - Compliance checklist
- `biometric_specifics.csv` - Biometric fields

## Environment

`GEMINI_API_KEY` required in `.env`

Models: `gemini-3-pro-preview` (primary), `gemini-2.0-flash-exp` (fallback)
