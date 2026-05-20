# AI Agent Instructions for M&E Intelligence Agent

## Project overview
- This workspace contains the product requirements in `M&E Agent.md` and a FastAPI implementation under `app/`.
- The system is a Monitoring & Evaluation Intelligence Agent, not a chatbot.
- Its primary function is decision intelligence for program management, using Google Sheets as the live data source.

## What the agent should know
- The system must fetch all sheets in the workbook on every trigger event.
- Analysis must be full-workbook and cross-sheet; a status change in the activity tracker only initiates the workflow.
- Sheet classification must be dynamic and structure-based, not name-based.
- Output must be donor-grade, executive-level M&E reporting with causal analysis and actionable recommendations.
- The agent should treat the workbook as a unified project intelligence system.

## Implementation guidance for coding tasks
- Use the existing Python/FastAPI implementation unless the user explicitly requests another stack.
- Keep changes aligned with the current pipeline:
  - Google Sheets API ingestion
  - sheet structure inference and classification
  - conversion into a unified project state model
  - analytical engine for schedule, KPI, risk, budget, workplan, issues, and dependency analysis
  - PDF report generation, branded email delivery, escalation alerts, and recommendation synthesis
- Do not introduce unrelated frameworks or new architecture without a clear implementation reason.

## Known constraints and priorities
- Must analyze all sheets, not just the trigger sheet.
- Must perform causal inference, dependency-aware reasoning, and system-level interpretation.
- Recommendations must be operational, prioritized, and mapped to specific issues.
- Reports must include structured sections like executive summary, performance analysis, risks, budget, and recommendations.

## Useful reference
- See `M&E Agent.md` for the full product requirements and core mission.
