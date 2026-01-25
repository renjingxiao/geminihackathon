# Automatic Logging Plugin

**EU AI Act Article 12: Logging & Traceability System**

A Python middleware plugin for automatic logging, real-time monitoring, and AI-powered compliance auditing.

## Overview

This plugin ensures your AI system complies with EU AI Act Article 12 requirements by:

- **Automatic Recording**: Logs all AI operations with privacy-preserving SHA-256 hashing
- **Real-time Monitoring**: Watchdog detects latency issues (>5s) and DOS attacks
- **AI Auditing**: Gemini LLM analyzes logs and generates compliance reports

## Quick Start

### Installation

```bash
pip install google-generativeai openpyxl pandas python-dotenv
```

### Environment Setup

```bash
# Add to your .env file
GEMINI_API_KEY=your_api_key_here
```

## Integration Guide

### Backend Integration (Python)

#### Option 1: Decorator (Recommended)

```python
from automatic_logging.scripts.logger import log_interaction

@log_interaction(system_version="1.0.0")
def chat_with_ai(user_input: str) -> str:
    # Your AI logic here
    response = call_your_model(user_input)
    return response

# Every call is automatically logged!
result = chat_with_ai("What is Article 12?")
```

#### Option 2: Direct Logger

```python
from automatic_logging.scripts.logger import ComplianceLogger
from datetime import datetime

logger = ComplianceLogger(system_version="1.0.0")

# Log operations manually
start_time = datetime.now()
response = call_your_model(user_input)
end_time = datetime.now()

logger.log_operation(
    input_text=user_input,
    output_text=response,
    start_time=start_time,
    end_time=end_time
)

# Log risks/incidents
logger.log_risk(
    event_type="Risk",
    risk_category="Performance degradation",
    description="High latency detected: 7.2s",
    action_taken="Alert sent to admin"
)
```

### Frontend Integration

The frontend can trigger logging operations via API endpoints:

```javascript
// Example: Frontend calls backend API that uses the logger
async function sendMessage(userInput) {
    const response = await fetch('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ message: userInput })
    });
    
    // Backend automatically logs via @log_interaction decorator
    return response.json();
}

// Example: Trigger compliance report generation
async function generateComplianceReport() {
    const response = await fetch('/api/compliance/audit', {
        method: 'POST'
    });
    return response.json(); // Returns path to generated report
}
```

### Flask/FastAPI Backend Example

```python
from flask import Flask, request, jsonify
from automatic_logging.scripts.logger import log_interaction, ComplianceLogger
from automatic_logging.scripts.auditor import audit_logs
from automatic_logging.scripts.utils import consolidate_to_excel

app = Flask(__name__)
logger = ComplianceLogger(system_version="1.0.0")

@app.route('/api/chat', methods=['POST'])
@log_interaction(system_version="1.0.0")
def chat(user_input=None):
    user_input = request.json.get('message')
    response = your_ai_model(user_input)
    return jsonify({"response": response})

@app.route('/api/compliance/audit', methods=['POST'])
def run_audit():
    report_path = audit_logs()
    return jsonify({"report": report_path})

@app.route('/api/compliance/export', methods=['POST'])
def export_excel():
    excel_path = consolidate_to_excel()
    return jsonify({"excel": str(excel_path)})
```

## Output Files

| File | Location | Description |
|------|----------|-------------|
| `Record_Keeping_Logging_Art12.xlsx` | `Project/Output/` | Consolidated 4-sheet workbook |
| `Record_Keeping_Logging_Art12_Report.md` | `Project/Output/` | AI-generated compliance report |
| `operational_logs.csv` | `automatic-logging/Output/` | Internal operation logs |
| `risk_logs.csv` | `automatic-logging/Output/` | Internal risk/incident logs |

## Components

| Component | File | Purpose |
|-----------|------|---------|
| Logger | `scripts/logger.py` | Core middleware + `@log_interaction` decorator |
| Watchdog | `scripts/watchdog.py` | Real-time latency & DOS detection |
| Auditor | `scripts/auditor.py` | Gemini LLM compliance analysis |
| Utils | `scripts/utils.py` | Hashing, CSV ops, Excel consolidation |
| Models | `scripts/models.py` | Data classes for log entries |

## Testing

```bash
cd scripts
python test_logging_system.py  # Run unit tests
python seed_data.py            # Generate mock data
```

## Models Used

- **Primary**: `gemini-3-pro-preview`
- **Fallback**: `gemini-2.0-flash-exp`

## License

Part of the Gemini Hackathon project.
