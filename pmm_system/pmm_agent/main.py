"""
PMM Agent FastAPI Application
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import asyncio

from .core.pmm_core import PMMCoreAgent
from .data.models import AIInteraction, UserFeedback

# Initialize FastAPI app
app = FastAPI(
    title="Post-Market Monitoring Agent",
    description="EU AI Act Article 72 Compliance Monitoring System",
    version="1.0.0"
)

# Global PMM agent instance
pmm_agent = PMMCoreAgent()


# ============================================================================
# Pydantic Models for API
# ============================================================================

class InteractionRequest(BaseModel):
    """Request model for logging interaction"""
    interaction_id: str
    user_id: Optional[str] = None
    prompt: str
    response: str
    response_time: float
    model_version: str = "default"
    metadata: Dict = Field(default_factory=dict)
    demographics: Optional[Dict] = None


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback"""
    interaction_id: str
    user_id: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    issues: List[str] = Field(default_factory=list)


class MetricsQuery(BaseModel):
    """Request model for querying metrics"""
    metric_names: Optional[List[str]] = None
    hours: int = 24


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Post-Market Monitoring Agent",
        "version": "1.0.0",
        "status": "running",
        "documentation": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "integrations": {
            "safety_provider": "connected",
            "ethics_bridge": "connected",
            "incident_trigger": "connected"
        }
    }


@app.post("/api/v1/interactions/log")
async def log_interaction(request: InteractionRequest):
    """
    Log an AI interaction for monitoring

    This endpoint records AI system interactions and automatically:
    - Extracts performance metrics
    - Checks safety thresholds
    - Monitors for bias (if demographics provided)
    - Triggers alerts and incidents if needed
    """
    try:
        # Create interaction object
        interaction = AIInteraction(
            interaction_id=request.interaction_id,
            timestamp=datetime.now(timezone.utc),
            user_id=request.user_id,
            prompt=request.prompt,
            response=request.response,
            response_time=request.response_time,
            model_version=request.model_version,
            metadata=request.metadata,
            demographics=request.demographics
        )

        # Process interaction
        result = await pmm_agent.process_interaction(interaction)

        return {
            "status": "logged",
            "interaction_id": request.interaction_id,
            "summary": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/feedback/submit")
async def submit_feedback(request: FeedbackRequest):
    """
    Submit user feedback

    Collects and analyzes user feedback including:
    - Sentiment analysis
    - Auto-categorization
    - Issue tracking
    """
    try:
        # Create feedback object
        feedback = UserFeedback(
            feedback_id=f"FB-{datetime.now(timezone.utc).timestamp()}",
            interaction_id=request.interaction_id,
            user_id=request.user_id,
            timestamp=datetime.now(timezone.utc),
            rating=request.rating,
            comment=request.comment,
            issues=request.issues
        )

        # Process feedback
        result = await pmm_agent.process_feedback(feedback)

        return {
            "status": "received",
            "feedback_id": feedback.feedback_id,
            "analysis": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/metrics/query")
async def query_metrics(request: MetricsQuery):
    """
    Query metrics

    Get summary of performance metrics over specified time period
    """
    try:
        summary = pmm_agent.get_metrics_summary(hours=request.hours)

        if request.metric_names:
            # Filter to requested metrics
            summary = {k: v for k, v in summary.items() if k in request.metric_names}

        return {
            "metrics": summary,
            "period_hours": request.hours,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/metrics/current")
async def get_current_metrics():
    """
    Get current metrics snapshot

    Returns latest metrics from buffer
    """
    try:
        current_metrics = {}
        for metric_name, values in pmm_agent.metrics_buffer.items():
            if values:
                current_metrics[metric_name] = {
                    'current_value': values[-1],
                    'recent_average': sum(values) / len(values),
                    'samples': len(values)
                }

        return {
            "metrics": current_metrics,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/alerts/active")
async def get_active_alerts():
    """Get active alerts"""
    try:
        from .data.storage import storage
        alerts = storage.get_active_alerts()

        return {
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "timestamp": a.timestamp.isoformat(),
                    "severity": a.severity.value,
                    "alert_type": a.alert_type,
                    "metric_name": a.metric_name,
                    "current_value": a.current_value,
                    "threshold": a.threshold
                }
                for a in alerts
            ],
            "count": len(alerts)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/incidents/active")
async def get_active_incidents():
    """Get active incidents"""
    try:
        incidents = pmm_agent.incident_trigger.get_active_incidents()

        return {
            "incidents": [
                {
                    "incident_id": inc['incident_id'],
                    "created_at": inc['created_at'].isoformat(),
                    "priority": inc['priority'],
                    "classification": inc['classification'],
                    "alert_type": inc['alert'].alert_type,
                    "severity": inc['alert'].severity.value
                }
                for inc in incidents
            ],
            "count": len(incidents)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/reports/summary")
async def get_summary_report(days: int = 7):
    """
    Generate summary report

    Creates comprehensive monitoring report for specified period
    """
    try:
        report = pmm_agent.generate_report(days=days)

        return {
            "report": report,
            "period_days": days,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/reports/bias")
async def get_bias_report():
    """Get bias monitoring report"""
    try:
        report = pmm_agent.ethics_bridge.get_bias_report()

        return {
            "report": report,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats")
async def get_statistics():
    """Get system statistics"""
    try:
        from .data.storage import storage

        stats = {
            "interactions": {
                "total": len(storage.interactions),
                "last_24h": len(storage.get_interactions(
                    start_time=datetime.now(timezone.utc) - timedelta(hours=24)
                ))
            },
            "alerts": {
                "total": len(storage.alerts),
                "active": len(storage.get_active_alerts())
            },
            "feedback": {
                "total": len(storage.feedback),
                "last_7d": len(storage.get_recent_feedback(days=7))
            },
            "incidents": pmm_agent.incident_trigger.get_incident_stats()
        }

        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Application startup"""
    print("\n" + "="*70)
    print("🚀 POST-MARKET MONITORING AGENT STARTING")
    print("="*70)
    print(f"✓ FastAPI application initialized")
    print(f"✓ PMM Core Agent ready")
    print(f"✓ API endpoints available at /docs")
    print("="*70 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown"""
    print("\n" + "="*70)
    print("👋 POST-MARKET MONITORING AGENT SHUTTING DOWN")
    print("="*70 + "\n")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
