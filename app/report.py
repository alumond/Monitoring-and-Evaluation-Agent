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
    dependency = analytics.get("dependency", {})
    data_quality = analytics.get("data_quality", [])
    schedule = analytics.get("schedule", {})

    def indicator_status(performance: float) -> str:
        if performance >= 100.0:
            return "Green / on track"
        if performance >= 80.0:
            return "Amber / at risk"
        return "Red / off track"

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
    if title == "Logframe Performance Analysis":
        return (
            "The logframe should be read as the strategic results frame for this cycle. Where indicators, activities, "
            "risks, and issues are present, management should review whether implementation progress is still credible "
            "against the intended outputs and outcomes."
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
        rows = [
            "| Indicator | Actual Value | Performance vs Target | Status |",
            "| --- | ---: | ---: | --- |",
        ]
        for item in kpi.get("performance", [])[:8]:
            performance = float(item.get("performance_percent", 0) or 0)
            rows.append(
                f"| {item.get('indicator', 'Indicator')} | {item.get('actual', 0):,.2f} | "
                f"{performance:.1f}% achievement against {item.get('target', 0):,.2f} target | "
                f"{indicator_status(performance)} |"
            )
        if len(rows) > 2:
            return "\n".join(rows)
        return (
            f"The KPI tracker contains {kpi.get('indicator_count', 0)} indicators, with "
            f"{kpi.get('on_track_count', 0)} currently at or above target. Indicator-level actuals and targets "
            "should be validated before donor submission."
        )
    if title == "Risk & Bottleneck Analysis":
        high_risks = risk.get("high_risk_count", 0)
        blocked = dependency.get("blocked_activity_count", 0)
        overdue = schedule.get("overdue_count", 0)
        callouts = []
        if high_risks:
            callouts.append(
                f"> **Critical risk exposure:** {high_risks} high-severity risk(s) require management attention.\n"
                "> **Implication:** Delivery confidence may weaken if mitigation owners and timelines are not confirmed.\n"
                "> **Action:** Review mitigation status and escalate unresolved controls in the next management meeting."
            )
        if blocked or overdue:
            callouts.append(
                f"> **Implementation bottleneck:** {blocked} blocked activity(ies) and {overdue} overdue activity(ies) are visible in the current data.\n"
                "> **Implication:** Downstream outputs may slip if dependencies remain unresolved.\n"
                "> **Action:** Reconfirm owners, unblock critical path dependencies, and reset delivery dates where needed."
            )
        if callouts:
            return "\n\n".join(callouts)
        return (
            f"The risk register contains {risk.get('risk_count', 0)} risks, including "
            f"{risk.get('high_risk_count', 0)} high-severity risks requiring management attention."
        )
    if title == "Budget & Resource Utilization":
        return (
            f"The budget tracker shows total budget of {budget.get('total_budget', 0):,.2f}, expenditure of "
            f"{budget.get('total_expenditure', 0):,.2f}, and utilization of {budget.get('utilization_percent', 0)}%."
        )
    if title == "Data Quality Assessment":
        if data_quality:
            return (
                f"{len(data_quality)} data quality issue(s) were detected. These should be resolved before external "
                "circulation so the report remains auditable and donor-ready."
            )
        return "No material workbook coverage gaps were detected in the current analytics summary."
    if title == "Dependency & Impact Analysis":
        return (
            f"The dependency analysis shows {dependency.get('blocked_activity_count', 0)} blocked activity(ies). "
            "Management should review whether these bottlenecks affect milestone sequencing, budget absorption, "
            "and indicator achievement."
        )
    if title == "Forecasting & Predictive Insights":
        return (
            "Forward-looking risk should be interpreted through the combined movement of activity completion, "
            "budget utilization, open issues, unresolved dependencies, and KPI achievement. Slippage in two or more "
            "areas should trigger a management review before the next reporting cycle."
        )
    if title == "Recommendations & Corrective Action Plan":
        return (
            "- **Immediate action:** Confirm owners and due dates for overdue, blocked, or high-risk items.\n"
            "- **Management action:** Review off-track indicators against activity and dependency constraints.\n"
            "- **Donor-readiness action:** Resolve material data quality gaps before formal report circulation."
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
        sections = [
            {
                "title": title,
                "body": narrative if title == "Executive Summary" and narrative.strip() else _fallback_section_body(title, analytics, project_state),
            }
            for title in SECTION_TITLES
        ]

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
