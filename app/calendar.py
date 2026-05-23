from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import get_settings
from .connectors import _install_google_sheets_dns_fallback


def _parse_recipients(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _parse_due_date(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class GoogleCalendarReminder:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        _install_google_sheets_dns_fallback()
        credentials = service_account.Credentials.from_service_account_file(
            self.settings.google_service_account_file,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        self.service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def _reminder_start(self, recommendations: List[Dict[str, Any]]) -> datetime:
        due_dates = [
            parsed
            for parsed in (_parse_due_date(item.get("due_date")) for item in recommendations)
            if parsed is not None
        ]
        target_date = min(due_dates) if due_dates else date.today() + timedelta(days=self.settings.google_calendar_reminder_days)
        if target_date < date.today():
            target_date = date.today()
        reminder_hour = max(0, min(int(self.settings.google_calendar_reminder_hour), 23))
        return datetime.combine(target_date, time(hour=reminder_hour))

    def _attendees(self, fallback_recipients: List[str]) -> List[Dict[str, str]]:
        configured = _parse_recipients(self.settings.google_calendar_attendees)
        emails = configured or fallback_recipients
        return [{"email": email} for email in emails]

    def _share_calendar(self, emails: List[str]) -> List[Dict[str, str]]:
        shared = []
        for email in emails:
            try:
                self.service.acl().insert(
                    calendarId=self.settings.google_calendar_id,
                    body={
                        "role": "reader",
                        "scope": {"type": "user", "value": email},
                    },
                    sendNotifications=True,
                ).execute()
                shared.append({"email": email, "status": "shared"})
            except HttpError as exc:
                if getattr(exc, "status_code", None) == 409 or "already exists" in str(exc).lower():
                    shared.append({"email": email, "status": "already_shared"})
                else:
                    shared.append({"email": email, "status": "failed", "reason": str(exc)})
        return shared

    def create_decision_reminder(
        self,
        decision: Dict[str, Any],
        recipients: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not self.settings.google_calendar_enabled:
            return {"status": "skipped", "reason": "Google Calendar reminders are disabled."}
        if not self.settings.google_calendar_id:
            return {"status": "skipped", "reason": "GOOGLE_CALENDAR_ID is not configured."}

        recipients = recipients or []
        recommendations = decision.get("recommendations", [])
        findings = decision.get("findings", [])
        start_at = self._reminder_start(recommendations)
        end_at = start_at + timedelta(minutes=45)
        top_findings = "\n".join(
            f"- [{item.get('severity', 'low').upper()}] {item.get('title', '')}: {item.get('details', '')}"
            for item in findings[:5]
        )
        top_actions = "\n".join(
            f"- {item.get('responsible_unit', 'Unassigned')}: {item.get('recommendation', '')} "
            f"Due: {item.get('due_date', 'Not set')}"
            for item in recommendations[:8]
        )
        description = (
            f"{decision.get('summary', 'M&E corrective action follow-up is required.')}\n\n"
            f"Priority findings:\n{top_findings or '- No findings provided.'}\n\n"
            f"Corrective actions:\n{top_actions or '- No corrective actions provided.'}"
        )
        attendees = self._attendees(recipients)
        event = {
            "summary": f"M&E Corrective Action Follow-up - {self.settings.project_name}",
            "description": description,
            "start": {
                "dateTime": start_at.isoformat(),
                "timeZone": self.settings.google_calendar_timezone,
            },
            "end": {
                "dateTime": end_at.isoformat(),
                "timeZone": self.settings.google_calendar_timezone,
            },
            "attendees": attendees,
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},
                    {"method": "popup", "minutes": 60},
                ],
            },
        }
        shared_calendar = []
        invite_email = {"status": "not_sent"}
        try:
            created = self.service.events().insert(
                calendarId=self.settings.google_calendar_id,
                body=event,
                sendUpdates=self.settings.google_calendar_send_updates,
            ).execute()
            attendee_mode = "invited"
        except HttpError as exc:
            if "Service accounts cannot invite attendees" not in str(exc):
                raise
            event.pop("attendees", None)
            shared_calendar = self._share_calendar([item["email"] for item in attendees])
            created = self.service.events().insert(
                calendarId=self.settings.google_calendar_id,
                body=event,
                sendUpdates="none",
            ).execute()
            attendee_mode = "calendar_shared"
            try:
                from .emailer import EmailDelivery

                invite_email = EmailDelivery(self.settings).send_calendar_invite(
                    subject=event["summary"],
                    description=description,
                    start_at=start_at,
                    end_at=end_at,
                    recipients=[item["email"] for item in attendees],
                    uid=f"{created.get('id', 'me-reminder')}@{self.settings.google_calendar_id}",
                )
            except Exception as invite_exc:
                invite_email = {
                    "status": "failed",
                    "reason": f"Calendar invite email failed: {invite_exc}",
                }
        return {
            "status": "created",
            "attendee_mode": attendee_mode,
            "shared_calendar": shared_calendar,
            "invite_email": invite_email,
            "event_id": created.get("id", ""),
            "html_link": created.get("htmlLink", ""),
            "start": created.get("start", {}),
        }

    def create_escalation_reminder(
        self,
        missed_targets: List[Dict[str, Any]],
        root_causes: List[str],
        corrective_actions: List[str],
        recipients: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        findings = [
            {
                "severity": "high" if float(item.get("performance_percent", 0) or 0) >= 70 else "critical",
                "title": f"KPI target breach: {item.get('indicator', 'Indicator')}",
                "details": (
                    f"Actual Value {float(item.get('actual', 0) or 0):,.2f}; "
                    f"Performance vs Target {float(item.get('performance_percent', 0) or 0):.1f}% "
                    f"against {float(item.get('target', 0) or 0):,.2f} target."
                ),
            }
            for item in missed_targets
        ]
        due_date = (date.today() + timedelta(days=self.settings.google_calendar_reminder_days)).isoformat()
        recommendations = [
            {
                "responsible_unit": "Program Manager" if index == 0 else "M&E Lead" if index == 1 else "Operations Lead",
                "recommendation": action,
                "due_date": due_date,
            }
            for index, action in enumerate(corrective_actions)
        ]
        decision = {
            "summary": (
                f"{len(missed_targets)} KPI target breach(es) require corrective action. "
                f"Likely root causes: {'; '.join(root_causes)}."
            ),
            "findings": findings,
            "recommendations": recommendations,
        }
        return self.create_decision_reminder(decision, recipients or [])
