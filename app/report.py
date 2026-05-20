from datetime import datetime
import re
from typing import Any, Dict, List


SECTION_TITLES = [
    "Executive Summary",
    "Project Metadata & Governance Context",
    "Activity Implementation Analysis",
    "Workplan Analysis",
    "Logframe Performance Analysis",
    "Indicator Performance Analysis",
    "Risk & Bottleneck Analysis",
    "Issues Log Analysis",
    "Budget & Resource Utilization",
    "Data Quality Assessment",
    "Dependency & Impact Analysis",
    "Forecasting & Predictive Insights",
    "Recommendations & Corrective Action Plan",
]


def _clean_heading(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"^#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"^\d+[\).\s-]+", "", cleaned)
    cleaned = cleaned.strip("*:_- ")
    return re.sub(r"\s+", " ", cleaned)


def _match_section_title(line: str) -> str:
    heading = _clean_heading(line)
    normalized = heading.lower().replace(" and ", " & ")
    for title in SECTION_TITLES:
        expected = title.lower().replace(" and ", " & ")
        if normalized == expected:
            return title
    return ""


def split_narrative_sections(narrative: str) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    current_title = ""
    current_lines: List[str] = []

    for line in narrative.splitlines():
        matched_title = _match_section_title(line)
        if matched_title:
            if current_title:
                sections[current_title] = current_lines
            current_title = matched_title
            current_lines = []
            continue
        if current_title:
            current_lines.append(line)

    if current_title:
        sections[current_title] = current_lines

    return {title: "\n".join(lines).strip() for title, lines in sections.items()}


def _fallback_section_body(title: str, analytics: Dict[str, Any], project_state: Dict[str, Any]) -> str:
    counts = project_state.get("counts", {})
    metadata = analytics.get("metadata", {})
    completion = analytics.get("completion", {})
    workplan = analytics.get("workplan", {})
    issues = analytics.get("issues", {})
    budget = analytics.get("budget", {})
    risk = analytics.get("risk", {})
    kpi = analytics.get("kpi", {})

    if title == "Project Metadata & Governance Context":
        details = [
            f"Project: {metadata.get('project_name') or project_state.get('project_name', 'Not specified')}",
            f"Code: {metadata.get('project_code') or 'Not specified'}",
            f"Implementing partner: {metadata.get('implementing_partner') or 'Not specified'}",
            f"Donor: {metadata.get('donor') or 'Not specified'}",
            f"Reporting period: {metadata.get('reporting_period') or 'Not specified'}",
        ]
        return "\n".join(f"- {item}" for item in details)
    if title == "Workplan Analysis":
        return (
            f"The workplan module contains {workplan.get('workplan_item_count', 0)} planned items across "
            f"{len(workplan.get('quarter_counts', {}))} active quarters. Quarter marker completion is "
            f"{workplan.get('quarter_completion_percent', 0)}%, with {workplan.get('partial_quarter_markers', 0)} "
            "partial implementation markers requiring follow-up."
        )
    if title == "Issues Log Analysis":
        return (
            f"The issues log contains {issues.get('issue_count', 0)} issues. "
            f"{issues.get('open_issue_count', 0)} remain open, including "
            f"{issues.get('high_open_issue_count', 0)} high-severity open issues. "
            "Open items should be reviewed against owner assignments, target dates, and their dependency impact."
        )
    if title == "Activity Implementation Analysis":
        return (
            f"The activity tracker contains {completion.get('total_activities', counts.get('activities', 0))} activities. "
            f"{completion.get('completed_activities', 0)} are complete, representing "
            f"{completion.get('percent_complete', 0)}% completion."
        )
    if title == "Indicator Performance Analysis":
        return (
            f"The KPI tracker contains {kpi.get('indicator_count', 0)} indicators, with "
            f"{kpi.get('on_track_count', 0)} currently at or above target."
        )
    if title == "Risk & Bottleneck Analysis":
        return (
            f"The risk register contains {risk.get('risk_count', 0)} risks, including "
            f"{risk.get('high_risk_count', 0)} high-severity risks requiring management attention."
        )
    if title == "Budget & Resource Utilization":
        return (
            f"The budget tracker shows total budget of {budget.get('total_budget', 0):,.2f}, expenditure of "
            f"{budget.get('total_expenditure', 0):,.2f}, and utilization of {budget.get('utilization_percent', 0)}%."
        )
    return "No additional section-specific narrative was generated for this reporting area."


def build_report_sections(narrative: str, analytics: Dict[str, Any], project_state: Dict[str, Any]) -> Dict[str, Any]:
    parsed_sections = split_narrative_sections(narrative)
    if parsed_sections:
        sections = [
            {
                "title": title,
                "body": parsed_sections.get(title) or _fallback_section_body(title, analytics, project_state),
            }
            for title in SECTION_TITLES
        ]
    else:
        sections = [{"title": "Executive Summary", "body": narrative}]

    summary = {
        "project": project_state.get("counts", {}),
        "analytics": analytics,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    return {
        "title": project_state.get("project_name", "M&E Intelligence Report"),
        "summary": summary,
        "sections": sections,
    }


def assemble_report_text(report: Dict[str, Any]) -> str:
    lines: List[str] = [f"{report['title']}", "", "Report Summary:"]
    lines.append(str(report["summary"]))
    for section in report["sections"]:
        lines.append("\n" + section["title"])
        lines.append(section["body"])
    return "\n".join(lines)
