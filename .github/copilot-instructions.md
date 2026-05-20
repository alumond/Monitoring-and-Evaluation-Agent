# Copilot Instructions for M&E Intelligence Agent

## Workspace context
- This repository contains the product requirements in `M&E Agent.md` and a Python/FastAPI implementation under `app/`.
- The system is a Monitoring & Evaluation Intelligence Agent that analyzes Google Sheets data and produces executive-grade M&E reports.

## Primary guidance for coding agents
- Always reference `M&E Agent.md` as the source of requirements.
- Use the existing Python/FastAPI architecture unless the user explicitly requests another stack.
- Do not invent project-specific source files or architecture beyond what the document and implementation support.
- Keep changes aligned with the current app modules for ingestion, classification, normalization, analytics, PDF rendering, email delivery, escalation, and audit logging.

## Key behavior requirements
- The agent must treat the workbook as a unified project intelligence system.
- The system must fetch and analyze ALL sheets on every trigger event.
- The trigger sheet is only an event initiator; analysis must not be limited to it.
- Sheet classification must be dynamic and based on structure, not sheet names.
- Output must be donor-grade, executive-level M&E reporting with causal analysis and actionable recommendations.

## Implementation focus areas
- Google Sheets integration: data ingestion via the Google Sheets API, full-workbook retrieval, and sheet metadata extraction.
- Sheet classification: infer types such as metadata, logframe, activity tracker/Gantt, workplan, KPI tracker, risk register, issues log, and budget sheet from headers and values.
- Unified model: convert raw sheet data into a single structured state model before reasoning.
- Analytics engine: perform schedule variance, KPI performance, risk scoring, dependency bottleneck detection, budget utilization, and data validation.
- Report generation: produce a structured branded PDF with executive summary, visual dashboards, analysis sections, risks, budget, issues, and prioritized recommendations.
- Email delivery: send branded HTML email notifications with clean plain-text fallbacks.
- Escalation: use `/escalation/trigger` for KPI target breaches and operational action alerts.

## Recommended task handling
- Prefer scoped changes to the existing modules over new frameworks or broad rewrites.
- Keep secrets, service account JSON files, generated PDFs, logs, databases, and `.env` out of Git.
- If asked for design or API definitions, keep them aligned to the project’s M&E intelligence mission.

## Useful reference
- See `M&E Agent.md` for full product requirements and core mission.
