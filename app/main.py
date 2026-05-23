import os
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from .config import get_settings
from .emailer import EmailDelivery
from .audit import AuditService
from .calendar import GoogleCalendarReminder
from .escalation import assess_escalation, build_escalation_message
from .intelligence_cycle import (
    ActivityTrackerNotFound,
    IntelligenceCycleRunner,
    MissingConfigurationError,
    parse_recipients,
)
from .scheduler import AutonomousCycleScheduler

app = FastAPI(title="M&E Intelligence Engine")
settings = get_settings()
audit_service = AuditService(settings)
autonomous_scheduler = AutonomousCycleScheduler(settings, audit_service)


class TriggerPayload(BaseModel):
    changed_sheet_title: Optional[str] = None
    changed_column: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_range: Optional[str] = None
    changed_row_values: Optional[List[str]] = None
    event_timestamp: Optional[str] = None


class SheetsWebhookPayload(TriggerPayload):
    source: Optional[str] = "google_sheets_webhook"


@app.on_event("startup")
def startup_event() -> None:
    os.makedirs("reports", exist_ok=True)
    os.makedirs(os.path.dirname(settings.log_db_url.replace("sqlite:///", "")) or "./db", exist_ok=True)
    audit_service.init_db()
    autonomous_scheduler.start()


@app.on_event("shutdown")
def shutdown_event() -> None:
    autonomous_scheduler.stop()


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "M&E Intelligence Engine"}


def is_status_change(payload: TriggerPayload) -> bool:
    if payload.changed_column and "status" in payload.changed_column.lower():
        return True
    if payload.changed_range and "status" in payload.changed_range.lower():
        return True
    if payload.old_value != payload.new_value and payload.new_value is not None:
        return True
    return False


@app.post("/trigger")
def process_trigger(payload: TriggerPayload) -> dict:
    if not is_status_change(payload):
        return {"status": "ignored", "reason": "Event does not appear to be a status change."}

    runner = IntelligenceCycleRunner(settings, audit_service)
    try:
        return runner.run(
            mode="trigger",
            trigger_context=payload.model_dump(),
            force_report=True,
        )
    except ActivityTrackerNotFound as exc:
        raise HTTPException(status_code=404, detail="No activity tracker sheet found in workbook.")
    except MissingConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/escalation/trigger")
def process_escalation(payload: TriggerPayload) -> dict:
    if not settings.escalation_enabled:
        return {
            "status": "disabled",
            "reason": "Escalation workflow is not enabled in configuration.",
        }

    runner = IntelligenceCycleRunner(settings, audit_service)
    try:
        intelligence = runner.load_project_intelligence()
    except ActivityTrackerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    analytics = intelligence["analytics"]

    escalation_data = assess_escalation(analytics, settings.escalation_kpi_threshold)
    if not escalation_data["should_escalate"]:
        return {
            "status": "no_escalation",
            "reason": "No missed KPI targets above the escalation threshold were found.",
            "analytics_summary": analytics,
        }

    recipients = parse_recipients(settings.escalation_recipients)
    if not recipients:
        raise HTTPException(status_code=400, detail="No escalation recipients configured.")

    subject, body, html_body = build_escalation_message(
        escalation_data["missed_targets"],
        escalation_data["root_causes"],
        escalation_data["corrective_actions"],
        settings,
    )

    email_delivery = EmailDelivery(settings)
    email_result = email_delivery.send_email(subject, body, recipients, html_body=html_body)
    if settings.google_calendar_enabled:
        try:
            calendar_result = GoogleCalendarReminder(settings).create_escalation_reminder(
                escalation_data["missed_targets"],
                escalation_data["root_causes"],
                escalation_data["corrective_actions"],
                recipients,
            )
        except Exception as exc:
            calendar_result = {
                "status": "failed",
                "reason": f"Google Calendar reminder creation failed: {exc}",
            }
    else:
        calendar_result = {"status": "skipped", "reason": "Google Calendar reminders are disabled."}

    audit_service.log_escalation(
        escalation_type="kpi_escalation",
        reason="; ".join(escalation_data["root_causes"]),
        recipients=recipients,
        details=escalation_data,
    )

    return {
        "status": "escalation_sent",
        "email_status": email_result,
        "calendar_status": calendar_result,
        "escalation_details": escalation_data,
    }


@app.post("/autonomy/run")
def run_autonomous_cycle(
    dry_run: bool = Query(
        False,
        description="Analyze and select actions without generating reports, sending email, writing to Sheets, or persisting run memory.",
    )
) -> dict:
    runner = IntelligenceCycleRunner(settings, audit_service)
    try:
        return runner.run(
            mode="autonomous",
            trigger_context={
                "source": "manual_autonomy_endpoint",
                "event_timestamp": datetime.utcnow().isoformat() + "Z",
                "dry_run": dry_run,
            },
            force_report=settings.autonomous_always_send_report,
            dry_run=dry_run,
        )
    except ActivityTrackerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MissingConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/webhooks/google-sheets/change")
def process_google_sheets_webhook(payload: SheetsWebhookPayload) -> dict:
    payload_data = payload.model_dump()
    status_change = is_status_change(payload)
    runner = IntelligenceCycleRunner(settings, audit_service)
    try:
        return runner.run(
            mode="trigger" if status_change else "autonomous",
            trigger_context={
                **payload_data,
                "source": payload.source or "google_sheets_webhook",
                "event_timestamp": payload.event_timestamp or datetime.utcnow().isoformat() + "Z",
                "status_change": status_change,
            },
            force_report=status_change,
        )
    except ActivityTrackerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MissingConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/autonomy/status")
def get_autonomy_status() -> dict:
    latest_memory = audit_service.get_latest_agent_memory()
    return {
        "scheduler": autonomous_scheduler.status(),
        "latest_memory": {
            "run_id": latest_memory.get("id") if latest_memory else None,
            "mode": latest_memory.get("mode") if latest_memory else None,
            "workbook_hash": latest_memory.get("workbook_hash") if latest_memory else None,
            "analytics_hash": latest_memory.get("analytics_hash") if latest_memory else None,
            "max_severity": latest_memory.get("max_severity") if latest_memory else None,
            "decision_summary": latest_memory.get("decision_summary") if latest_memory else None,
        },
    }
