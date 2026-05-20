import os
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .config import get_settings
from .connectors import GoogleSheetsConnector
from .classification import classify_workbook, find_activity_tracker
from .normalization import normalize_workbook
from .state import build_unified_project_state
from .analytics import compute_project_analytics
from .gemini import GeminiClient
from .report import build_report_sections
from .pdf import build_pdf_report
from .emailer import EmailDelivery
from .audit import AuditService
from .escalation import assess_escalation, build_escalation_message

app = FastAPI(title="M&E Intelligence Engine")
settings = get_settings()
audit_service = AuditService(settings)


class TriggerPayload(BaseModel):
    changed_sheet_title: Optional[str] = None
    changed_column: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_range: Optional[str] = None
    changed_row_values: Optional[List[str]] = None
    event_timestamp: Optional[str] = None


@app.on_event("startup")
def startup_event() -> None:
    os.makedirs("reports", exist_ok=True)
    os.makedirs(os.path.dirname(settings.log_db_url.replace("sqlite:///", "")) or "./db", exist_ok=True)
    audit_service.init_db()


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


def parse_recipients(recipient_list: str) -> List[str]:
    return [email.strip() for email in recipient_list.split(",") if email.strip()]


@app.post("/trigger")
def process_trigger(payload: TriggerPayload) -> dict:
    if not is_status_change(payload):
        return {"status": "ignored", "reason": "Event does not appear to be a status change."}

    connector = GoogleSheetsConnector(settings)
    workbook = connector.fetch_workbook()
    classified = classify_workbook(workbook)
    activity_tracker = find_activity_tracker(classified)
    if not activity_tracker:
        raise HTTPException(status_code=404, detail="No activity tracker sheet found in workbook.")

    normalized = normalize_workbook(workbook)
    unified_state = build_unified_project_state(normalized)
    unified_state["project_name"] = settings.project_name
    analytics = compute_project_analytics(unified_state)

    gemini = GeminiClient(settings)
    narrative = gemini.generate_report_text(analytics, unified_state)
    report = build_report_sections(narrative, analytics, unified_state)

    period = datetime.utcnow().strftime("%Y-%m-%d")
    filename = settings.report_filename_template.format(timestamp=datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"))
    pdf_path = os.path.join("reports", filename)
    build_pdf_report(report, pdf_path, settings.brand_logo_path, settings.project_name)

    recipients = [email.strip() for email in settings.default_recipients.split(",") if email.strip()]
    if not recipients:
        raise HTTPException(status_code=400, detail="No email recipients configured.")

    email_delivery = EmailDelivery(settings)
    subject = settings.report_subject_format.format(project_name=settings.project_name, period=period)
    body = f"Attached is the latest M&E intelligence report for {settings.project_name} on {period}."
    email_result = email_delivery.send_report(subject, body, pdf_path, recipients)

    audit_service.log_trigger(
        sheet_title=payload.changed_sheet_title or activity_tracker["title"],
        changed_column=payload.changed_column or "status",
        old_value=payload.old_value or "",
        new_value=payload.new_value or "",
        event_timestamp=payload.event_timestamp or datetime.utcnow().isoformat(),
        payload=payload.dict(),
    )
    audit_service.log_report(
        report_path=pdf_path,
        email_status=email_result.get("status", "unknown"),
        analytics=analytics,
        workbook=workbook,
        narrative=narrative,
    )

    return {
        "status": "processed",
        "report_path": pdf_path,
        "email_status": email_result,
        "analytics_summary": analytics,
    }


@app.post("/escalation/trigger")
def process_escalation(payload: TriggerPayload) -> dict:
    if not settings.escalation_enabled:
        return {
            "status": "disabled",
            "reason": "Escalation workflow is not enabled in configuration.",
        }

    connector = GoogleSheetsConnector(settings)
    workbook = connector.fetch_workbook()
    normalized = normalize_workbook(workbook)
    unified_state = build_unified_project_state(normalized)
    unified_state["project_name"] = settings.project_name
    analytics = compute_project_analytics(unified_state)

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

    audit_service.log_escalation(
        escalation_type="kpi_escalation",
        reason="; ".join(escalation_data["root_causes"]),
        recipients=recipients,
        details=escalation_data,
    )

    return {
        "status": "escalation_sent",
        "email_status": email_result,
        "escalation_details": escalation_data,
    }
