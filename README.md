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
- SQLite audit logging for traceability

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

## Notes

- The system always fetches all workbook sheets on trigger.
- It never sends raw spreadsheet rows to Gemini; only structured analytics and high-level project state are forwarded.
- Sheet type detection is based on header structure, not sheet names.
