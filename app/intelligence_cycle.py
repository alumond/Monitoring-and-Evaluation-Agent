import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .analytics import compute_project_analytics
from .audit import AuditService
from .calendar import GoogleCalendarReminder
from .classification import classify_workbook, find_activity_tracker
from .config import get_settings
from .connectors import GoogleSheetsConnector
from .decision import build_decision_notification, evaluate_decision_policy
from .emailer import EmailDelivery
from .gemini import GeminiClient
from .normalization import normalize_workbook
from .pdf import build_pdf_report
from .report import build_report_sections
from .state import build_unified_project_state


class ActivityTrackerNotFound(RuntimeError):
    pass


class MissingConfigurationError(RuntimeError):
    pass


def parse_recipients(recipient_list: str) -> List[str]:
    return [email.strip() for email in recipient_list.split(",") if email.strip()]


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _has_action(decision: Dict[str, Any], action_type: str) -> bool:
    return any(action.get("type") == action_type for action in decision.get("actions", []))


def _mark_action(decision: Dict[str, Any], action_type: str, status: str, details: Any = None) -> Dict[str, Any]:
    result = {
        "type": action_type,
        "status": status,
        "details": details or {},
    }
    for action in decision.get("actions", []):
        if action.get("type") == action_type:
            result.update({key: value for key, value in action.items() if key not in result})
            break
    return result


def _mark_planned_actions_for_dry_run(decision: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            **action,
            "status": "dry_run",
            "details": {
                "reason": "Dry run selected this action but did not execute it.",
            },
        }
        for action in decision.get("actions", [])
    ]


class IntelligenceCycleRunner:
    def __init__(self, settings=None, audit_service: Optional[AuditService] = None):
        self.settings = settings or get_settings()
        self.audit_service = audit_service or AuditService(self.settings)

    def load_project_intelligence(self) -> Dict[str, Any]:
        connector = GoogleSheetsConnector(self.settings)
        workbook = connector.fetch_workbook()
        classified = classify_workbook(workbook)
        activity_tracker = find_activity_tracker(classified)
        if not activity_tracker:
            raise ActivityTrackerNotFound("No activity tracker sheet found in workbook.")

        normalized = normalize_workbook(workbook)
        unified_state = build_unified_project_state(normalized)
        unified_state["project_name"] = self.settings.project_name
        analytics = compute_project_analytics(unified_state)
        return {
            "workbook": workbook,
            "classified": classified,
            "activity_tracker": activity_tracker,
            "normalized": normalized,
            "unified_state": unified_state,
            "analytics": analytics,
        }

    def _build_report(self, analytics: Dict[str, Any], unified_state: Dict[str, Any]) -> Dict[str, Any]:
        gemini = GeminiClient(self.settings)
        narrative = gemini.generate_report_text(analytics, unified_state)
        report = build_report_sections(narrative, analytics, unified_state)

        filename = self.settings.report_filename_template.format(
            timestamp=datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        )
        pdf_path = os.path.join("reports", filename)
        build_pdf_report(report, pdf_path, self.settings.brand_logo_path, self.settings.project_name)
        return {
            "narrative": narrative,
            "report": report,
            "pdf_path": pdf_path,
        }

    def _send_report(self, pdf_path: str, strict: bool) -> Dict[str, Any]:
        recipients = parse_recipients(self.settings.default_recipients)
        if not recipients:
            if strict:
                raise MissingConfigurationError("No email recipients configured.")
            return {"status": "skipped", "reason": "No default report recipients configured."}

        period = datetime.utcnow().strftime("%Y-%m-%d")
        subject = self.settings.report_subject_format.format(
            project_name=self.settings.project_name,
            period=period,
        )
        body = f"Attached is the latest M&E intelligence report for {self.settings.project_name} on {period}."
        email_delivery = EmailDelivery(self.settings)
        return email_delivery.send_report(subject, body, pdf_path, recipients)

    def _send_decision_email(self, decision: Dict[str, Any], action_type: str, strict: bool = False) -> Dict[str, Any]:
        if action_type == "send_escalation":
            recipients = parse_recipients(self.settings.escalation_recipients)
            notification = build_decision_notification(decision, self.settings, notification_type="escalation")
        else:
            configured = self.settings.autonomous_operational_alert_recipients or self.settings.default_recipients
            recipients = parse_recipients(configured)
            notification = build_decision_notification(decision, self.settings, notification_type="alert")

        if not recipients:
            if strict:
                raise MissingConfigurationError(f"No recipients configured for {action_type}.")
            return {"status": "skipped", "reason": f"No recipients configured for {action_type}."}

        email_delivery = EmailDelivery(self.settings)
        return email_delivery.send_email(
            notification["subject"],
            notification["body"],
            recipients,
            html_body=notification.get("html_body", ""),
        )

    def _writeback_recommendations(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.settings.agent_writeback_enabled:
            return {"status": "skipped", "reason": "Agent write-back is disabled."}
        try:
            connector = GoogleSheetsConnector(self.settings)
            return connector.append_agent_actions(recommendations)
        except Exception as exc:
            return {
                "status": "failed",
                "reason": f"Recommendation write-back failed: {exc}",
            }

    def _create_calendar_reminder(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        if not self.settings.google_calendar_enabled:
            return {"status": "skipped", "reason": "Google Calendar reminders are disabled."}
        recipients = parse_recipients(self.settings.google_calendar_attendees or self.settings.escalation_recipients)
        try:
            reminder = GoogleCalendarReminder(self.settings)
            return reminder.create_decision_reminder(decision, recipients)
        except Exception as exc:
            return {
                "status": "failed",
                "reason": f"Google Calendar reminder creation failed: {exc}",
            }

    def run(
        self,
        mode: str = "manual",
        trigger_context: Optional[Dict[str, Any]] = None,
        force_report: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        trigger_context = trigger_context or {}
        intelligence = self.load_project_intelligence()
        workbook = intelligence["workbook"]
        unified_state = intelligence["unified_state"]
        analytics = intelligence["analytics"]
        activity_tracker = intelligence["activity_tracker"]

        workbook_hash = _hash_payload(workbook)
        analytics_hash = _hash_payload(analytics)
        previous_memory = self.audit_service.get_latest_agent_memory()
        previous_analytics = (previous_memory or {}).get("analytics")
        previous_workbook_hash = (previous_memory or {}).get("workbook_hash", "")
        overdue_recommendations = self.audit_service.get_overdue_open_recommendations()

        decision = evaluate_decision_policy(
            analytics=analytics,
            previous_analytics=previous_analytics,
            overdue_recommendations=overdue_recommendations,
            workbook_hash=workbook_hash,
            previous_workbook_hash=previous_workbook_hash,
            mode=mode,
            settings=self.settings,
            force_report=force_report,
        )

        report_artifacts: Dict[str, Any] = {}
        action_results: List[Dict[str, Any]] = []
        strict_report_delivery = mode == "trigger" or force_report

        if dry_run:
            action_results = _mark_planned_actions_for_dry_run(decision)
            return {
                "status": "dry_run",
                "run_id": None,
                "mode": mode,
                "dry_run": True,
                "persisted": False,
                "report_path": "",
                "email_status": {"status": "not_sent", "reason": "Dry run did not send email."},
                "decision": decision,
                "actions": action_results,
                "analytics_summary": analytics,
            }

        if _has_action(decision, "generate_report") or _has_action(decision, "send_report"):
            report_artifacts = self._build_report(analytics, unified_state)
            action_results.append(
                _mark_action(
                    decision,
                    "generate_report",
                    "completed",
                    {"report_path": report_artifacts["pdf_path"]},
                )
            )

        if _has_action(decision, "send_report"):
            email_result = self._send_report(report_artifacts.get("pdf_path", ""), strict_report_delivery)
            action_results.append(_mark_action(decision, "send_report", email_result.get("status", "unknown"), email_result))

        if _has_action(decision, "send_escalation"):
            escalation_result = self._send_decision_email(decision, "send_escalation")
            action_results.append(
                _mark_action(decision, "send_escalation", escalation_result.get("status", "unknown"), escalation_result)
            )

        if _has_action(decision, "create_calendar_reminder"):
            calendar_result = self._create_calendar_reminder(decision)
            action_results.append(
                _mark_action(
                    decision,
                    "create_calendar_reminder",
                    calendar_result.get("status", "unknown"),
                    calendar_result,
                )
            )

        if _has_action(decision, "send_operational_alert"):
            alert_result = self._send_decision_email(decision, "send_operational_alert")
            action_results.append(
                _mark_action(decision, "send_operational_alert", alert_result.get("status", "unknown"), alert_result)
            )

        if _has_action(decision, "writeback_recommendations"):
            writeback_result = self._writeback_recommendations(decision.get("recommendations", []))
            action_results.append(
                _mark_action(
                    decision,
                    "writeback_recommendations",
                    writeback_result.get("status", "unknown"),
                    writeback_result,
                )
            )

        if _has_action(decision, "no_op"):
            action_results.append(_mark_action(decision, "no_op", "completed", {"reason": "No external action selected."}))

        run_id = self.audit_service.log_agent_run(
            mode=mode,
            status="completed",
            trigger_source=trigger_context.get("source", mode),
            trigger_context=trigger_context,
            workbook_hash=workbook_hash,
            analytics_hash=analytics_hash,
            decision=decision,
            action_results=action_results,
            analytics=analytics,
            workbook=workbook,
            state=unified_state,
        )

        if mode == "trigger":
            self.audit_service.log_trigger(
                sheet_title=trigger_context.get("changed_sheet_title") or activity_tracker["title"],
                changed_column=trigger_context.get("changed_column") or "status",
                old_value=trigger_context.get("old_value") or "",
                new_value=trigger_context.get("new_value") or "",
                event_timestamp=trigger_context.get("event_timestamp") or datetime.utcnow().isoformat(),
                payload=trigger_context,
            )

        if report_artifacts:
            send_report_result = next(
                (item for item in action_results if item.get("type") == "send_report"),
                {"status": "not_sent"},
            )
            self.audit_service.log_report(
                report_path=report_artifacts["pdf_path"],
                email_status=send_report_result.get("status", "unknown"),
                analytics=analytics,
                workbook=workbook,
                narrative=report_artifacts.get("narrative", ""),
            )

        return {
            "status": "processed",
            "run_id": run_id,
            "mode": mode,
            "report_path": report_artifacts.get("pdf_path", ""),
            "email_status": next(
                (item.get("details") for item in action_results if item.get("type") == "send_report"),
                {"status": "not_sent"},
            ),
            "decision": decision,
            "actions": action_results,
            "analytics_summary": analytics,
        }
