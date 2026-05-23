# M&E Intelligence Engine

A production-ready backend for a Monitoring & Evaluation intelligence platform that connects to Google Sheets, performs full workbook analysis, generates donor-grade narrative reports with Gemini reasoning, exports a branded PDF, and emails it to stakeholders.

## Features

- Google Sheets connector using service account authentication
- Dynamic sheet classification by header structure
- Unified project state normalization across all workbook tabs
- Deterministic analytics for schedule, KPI, risk, dependency, budget, and data quality
- Gemini Flash 2.5 Lite reasoning for executive narrative generation
- Structured M&E report generation
- PDF export with branding support
- Email delivery via SMTP
- Separate escalation workflow for operational action and KPI target breaches
- Optional Google Calendar corrective-action reminders for escalations
- SQLite audit logging for traceability
- Reusable intelligence-cycle service shared by trigger and autonomous runs
- Optional autonomous scheduler with memory-backed change detection
- Deterministic decision policy for reports, alerts, escalations, and recommendation write-back

## Installation

1. Create a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy the environment example and configure:

   ```bash
   cp .env.example .env
   ```

4. Populate `.env` with your Google service account key, spreadsheet ID, Gemini API URL/key, SMTP settings, and recipients.

## Running the service

Start the FastAPI app with Uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The service exposes:

- `GET /health` — service health check
- `POST /trigger` — trigger event endpoint for status updates
- `POST /escalation/trigger` — separate escalation endpoint for missed KPI target alerts
- `POST /autonomy/run` — run one autonomous intelligence cycle immediately
- `POST /autonomy/run?dry_run=true` — analyze and return planned autonomous actions without reports, emails, write-back, or memory persistence
- `POST /webhooks/google-sheets/change` — receive external Google Sheets change events and run the intelligence cycle immediately
- `GET /autonomy/status` — inspect scheduler status and latest agent memory

## Trigger payload example

```json
{
  "changed_sheet_title": "Activity Tracker",
  "changed_column": "Status",
  "old_value": "In Progress",
  "new_value": "Complete",
  "changed_range": "G12",
  "event_timestamp": "2026-05-20T10:30:00Z"
}
```

## Audit and logs

Audit records are stored in SQLite at the path configured by `LOG_DB_URL` (default: `./db/report_audit.db`). The system logs trigger events, workbook snapshots, analytics summaries, report output paths, and email status.

Autonomous runs also store durable memory in `agent_runs`, `workbook_snapshots`, `agent_findings`, `agent_recommendations`, and `agent_actions`. The decision policy compares the latest workbook hash and analytics against the previous completed agent run, then selects bounded actions:

- generate and send a report
- send an operational alert
- send an escalation alert
- write recommendations to the configured Google Sheet
- no-op while still recording memory

Autonomous scheduling is enabled with:

```bash
AUTONOMOUS_SCHEDULER_ENABLED=true
AUTONOMOUS_SCHEDULER_INTERVAL_SECONDS=3600
AUTONOMOUS_SCHEDULER_RUN_ON_STARTUP=true
```

Recommendation write-back appends recommendations to the configured `Agent Actions` tab when `AGENT_WRITEBACK_ENABLED=true`. The service account must have edit access to the workbook. If write-back fails because of permissions, report and escalation email delivery still proceed and the write-back failure is recorded as an action result.

Escalation reminders can also be created in Google Calendar. Enable them by sharing the target calendar with the service account and setting:

```bash
GOOGLE_CALENDAR_ENABLED=true
GOOGLE_CALENDAR_ID=your_shared_calendar_id@example.com
GOOGLE_CALENDAR_ATTENDEES=programme.manager@example.com,me.lead@example.com
GOOGLE_CALENDAR_TIMEZONE=Africa/Lagos
GOOGLE_CALENDAR_REMINDER_DAYS=3
GOOGLE_CALENDAR_REMINDER_HOUR=9
```

When enabled, the agent creates a corrective-action follow-up event after escalation, with email and popup reminders. Google blocks service accounts from directly inviting attendees unless Workspace Domain-Wide Delegation is enabled; when that happens, the agent shares the service-account calendar and sends a branded `.ics` calendar invitation email so recipients can add the reminder directly from Gmail or their device calendar app.

Before enabling live autonomous actions, test the policy safely:

```bash
curl -X POST "http://127.0.0.1:8000/autonomy/run?dry_run=true"
```

Dry runs fetch and analyze the live workbook, then return the action plan the decision policy would have executed. They do not generate a PDF, send email, write to Google Sheets, or update the agent's completed-run memory.

For near-real-time Google Sheets monitoring, connect an external Apps Script or automation to:

```bash
POST http://127.0.0.1:8000/webhooks/google-sheets/change
```

A status-change webhook is treated like the regular trigger path and forces report delivery. Other workbook-change webhooks run the autonomous decision policy and act when thresholds are breached.

## Branding

Reports and email notifications are branded as Almond Ai Consulting. The default logo path is:

```bash
BRAND_LOGO_PATH=./assets/Almond AI consulting.png
```

The same branding is used in PDF reports, report emails, operational alerts, and escalation notifications.

## Notes

- The system always fetches all workbook sheets on trigger.
- It never sends raw spreadsheet rows to Gemini; only structured analytics and high-level project state are forwarded.
- Sheet type detection is based on header structure, not sheet names.
