import html
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


BRAND_BLUE = "#004C86"
BRAND_RED = "#FF1F1F"
BRAND_DARK = "#24313D"
BRAND_MUTED = "#647282"
BRAND_LINE = "#D9E1EA"
BRAND_LIGHT = "#F5F8FB"


SEVERITY_RANK = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _safe_number(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _max_severity(findings: List[Dict[str, Any]]) -> str:
    if not findings:
        return "none"
    return max(findings, key=lambda item: SEVERITY_RANK.get(item.get("severity", "low"), 0)).get("severity", "low")


def _priority_for_severity(severity: str) -> str:
    if severity == "critical":
        return "High"
    if severity == "high":
        return "High"
    if severity == "medium":
        return "Medium"
    return "Low"


def _due_date_for_severity(severity: str) -> str:
    days = 2 if severity == "critical" else 5 if severity == "high" else 10 if severity == "medium" else 14
    return (datetime.utcnow().date() + timedelta(days=days)).isoformat()


def _append_issue(
    findings: List[Dict[str, Any]],
    recommendations: List[Dict[str, Any]],
    finding_key: str,
    category: str,
    severity: str,
    title: str,
    details: str,
    evidence: Dict[str, Any],
    responsible_unit: str,
    recommendation: str,
) -> None:
    findings.append(
        {
            "finding_key": finding_key,
            "category": category,
            "severity": severity,
            "title": title,
            "details": details,
            "evidence": evidence,
            "status": "open",
        }
    )
    recommendations.append(
        {
            "finding_key": finding_key,
            "priority": _priority_for_severity(severity),
            "responsible_unit": responsible_unit,
            "recommendation": recommendation,
            "due_date": _due_date_for_severity(severity),
            "status": "open",
        }
    )


def _previous_metric(previous_analytics: Optional[Dict[str, Any]], path: List[str], default: Any = 0) -> Any:
    current: Any = previous_analytics or {}
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def evaluate_decision_policy(
    analytics: Dict[str, Any],
    previous_analytics: Optional[Dict[str, Any]],
    overdue_recommendations: Optional[List[Dict[str, Any]]],
    workbook_hash: str,
    previous_workbook_hash: str,
    mode: str,
    settings: Any,
    force_report: bool = False,
) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []
    workbook_changed = bool(workbook_hash and workbook_hash != previous_workbook_hash)
    autonomous_mode = mode in {"scheduled", "autonomous"}
    live_mail_mode = autonomous_mode or mode == "trigger"
    overdue_recommendations = overdue_recommendations or []

    for indicator in analytics.get("kpi", {}).get("performance", []):
        target = _safe_number(indicator.get("target"))
        performance = _safe_number(indicator.get("performance_percent"))
        if target <= 0 or performance >= settings.escalation_kpi_threshold:
            continue
        severity = "critical" if performance < settings.decision_kpi_critical_threshold else "high"
        indicator_name = indicator.get("indicator") or indicator.get("indicator_id") or "Unnamed indicator"
        actual = _safe_number(indicator.get("actual"))
        gap = target - actual
        _append_issue(
            findings,
            recommendations,
            finding_key=f"kpi:{indicator.get('indicator_id', indicator_name)}",
            category="kpi",
            severity=severity,
            title=f"KPI below threshold: {indicator_name}",
            details=(
                f"Actual Value is {actual:,.2f}; Performance vs Target is {performance:.1f}% achievement "
                f"against {target:,.2f} target, leaving a {gap:,.2f} unit gap. This is below the configured "
                f"{settings.escalation_kpi_threshold:.1f}% escalation threshold."
            ),
            evidence=indicator,
            responsible_unit="M&E Unit",
            recommendation=(
                "Conduct a rapid variance review, validate field evidence, and agree a corrective action "
                "with the responsible implementation team for the underperforming indicator."
            ),
        )

    overdue_count = int(analytics.get("schedule", {}).get("overdue_count", 0) or 0)
    if overdue_count:
        severity = "high" if overdue_count >= settings.decision_overdue_high_count else "medium"
        previous_overdue = int(_previous_metric(previous_analytics, ["schedule", "overdue_count"], 0) or 0)
        trend = "increased" if overdue_count > previous_overdue else "remains active"
        _append_issue(
            findings,
            recommendations,
            finding_key="schedule:overdue",
            category="schedule",
            severity=severity,
            title=f"{overdue_count} overdue activities detected",
            details=f"Overdue activity count {trend}; previous run recorded {previous_overdue}.",
            evidence=analytics.get("schedule", {}),
            responsible_unit="Field Team",
            recommendation=(
                "Review overdue activities against the critical path, confirm owner constraints, and reset "
                "completion dates with explicit recovery actions."
            ),
        )

    blocked_count = int(analytics.get("dependency", {}).get("blocked_activity_count", 0) or 0)
    if blocked_count:
        _append_issue(
            findings,
            recommendations,
            finding_key="dependency:blocked",
            category="dependency",
            severity="high",
            title=f"{blocked_count} blocked activities require dependency resolution",
            details="Blocked or delayed activities are likely to affect downstream workplan execution.",
            evidence=analytics.get("dependency", {}),
            responsible_unit="Program Management",
            recommendation=(
                "Convene the owners of blocked activities, resolve inter-team dependencies, and protect "
                "downstream deliverables from schedule slippage."
            ),
        )

    high_risk_count = int(analytics.get("risk", {}).get("high_risk_count", 0) or 0)
    if high_risk_count:
        _append_issue(
            findings,
            recommendations,
            finding_key="risk:high_severity",
            category="risk",
            severity="high",
            title=f"{high_risk_count} high-severity risks require management attention",
            details="Risk exposure is above the management-action threshold.",
            evidence=analytics.get("risk", {}),
            responsible_unit="Program Management",
            recommendation=(
                "Activate mitigation owners for each high-severity risk and require dated mitigation "
                "updates before the next reporting cycle."
            ),
        )

    high_open_issue_count = int(analytics.get("issues", {}).get("high_open_issue_count", 0) or 0)
    if high_open_issue_count:
        _append_issue(
            findings,
            recommendations,
            finding_key="issues:high_open",
            category="issues",
            severity="high",
            title=f"{high_open_issue_count} high-severity issues remain open",
            details="Open high-severity issues require owner-level closure tracking.",
            evidence=analytics.get("issues", {}),
            responsible_unit="Operations Team",
            recommendation=(
                "Assign named owners and closure dates for high-severity issues, then review unresolved "
                "items in the next program management meeting."
            ),
        )

    budget = analytics.get("budget", {})
    utilization = _safe_number(budget.get("utilization_percent"))
    total_budget = _safe_number(budget.get("total_budget"))
    if total_budget > 0 and utilization < settings.decision_budget_low_utilization_threshold:
        _append_issue(
            findings,
            recommendations,
            finding_key="budget:low_utilization",
            category="budget",
            severity="medium",
            title="Budget utilization is below expected implementation pace",
            details=(
                f"Budget utilization is {utilization:.1f}%, below the configured "
                f"{settings.decision_budget_low_utilization_threshold:.1f}% threshold."
            ),
            evidence=budget,
            responsible_unit="Operations Team",
            recommendation=(
                "Review procurement, liquidation, and activity funding bottlenecks, then rephase resources "
                "toward activities that are ready for execution."
            ),
        )
    elif total_budget > 0 and utilization > settings.decision_budget_overrun_threshold:
        _append_issue(
            findings,
            recommendations,
            finding_key="budget:overrun",
            category="budget",
            severity="high",
            title="Budget utilization indicates possible overrun",
            details=(
                f"Budget utilization is {utilization:.1f}%, above the configured "
                f"{settings.decision_budget_overrun_threshold:.1f}% threshold."
            ),
            evidence=budget,
            responsible_unit="Operations Team",
            recommendation=(
                "Freeze non-essential spending against affected lines until finance validates expenditure, "
                "commitments, and available balances."
            ),
        )

    quality_issues = analytics.get("data_quality", [])
    if quality_issues:
        _append_issue(
            findings,
            recommendations,
            finding_key="data_quality:issues",
            category="data_quality",
            severity="medium",
            title=f"{len(quality_issues)} data quality issues detected",
            details="Missing or incomplete workbook structures reduce confidence in automated interpretation.",
            evidence={"issues": quality_issues},
            responsible_unit="M&E Unit",
            recommendation=(
                "Correct missing sheets, empty task names, and incomplete tracker fields before relying on "
                "the next generated donor report."
            ),
        )

    if overdue_recommendations:
        critical_overdue = [
            item for item in overdue_recommendations
            if str(item.get("priority", "")).strip().lower() == "high"
        ]
        severity = "critical" if critical_overdue else "high"
        _append_issue(
            findings,
            recommendations,
            finding_key="follow_up:overdue_recommendations",
            category="follow_up",
            severity=severity,
            title=f"{len(overdue_recommendations)} prior recommendations are overdue",
            details=(
                "The agent found open recommendations whose due dates have passed. "
                "These items require management follow-up before the next implementation cycle."
            ),
            evidence={"overdue_recommendations": overdue_recommendations[:20]},
            responsible_unit="Program Management",
            recommendation=(
                "Review overdue corrective actions, confirm completion evidence or blockers, and escalate "
                "unresolved high-priority items to the accountable unit lead."
            ),
        )

    max_severity = _max_severity(findings)
    max_rank = SEVERITY_RANK.get(max_severity, 0)
    report_required = force_report or settings.autonomous_always_send_report
    if autonomous_mode and settings.autonomous_report_on_findings and workbook_changed and max_rank >= SEVERITY_RANK["medium"]:
        report_required = True

    actions: List[Dict[str, Any]] = []
    if report_required:
        actions.append(
            {
                "type": "generate_report",
                "priority": _priority_for_severity(max_severity),
                "target": "pdf",
                "status": "planned",
            }
        )
        actions.append(
            {
                "type": "send_report",
                "priority": _priority_for_severity(max_severity),
                "target": "default_recipients",
                "status": "planned",
            }
        )

    if live_mail_mode and settings.escalation_enabled and max_rank >= SEVERITY_RANK["high"]:
        actions.append(
            {
                "type": "send_escalation",
                "priority": "High",
                "target": "escalation_recipients",
                "status": "planned",
            }
        )
        if settings.google_calendar_enabled:
            actions.append(
                {
                    "type": "create_calendar_reminder",
                    "priority": "High",
                    "target": settings.google_calendar_id or "google_calendar",
                    "status": "planned",
                }
            )

    if (
        autonomous_mode
        and settings.autonomous_operational_alerts_enabled
        and findings
        and not report_required
        and max_rank >= SEVERITY_RANK["medium"]
    ):
        actions.append(
            {
                "type": "send_operational_alert",
                "priority": _priority_for_severity(max_severity),
                "target": "operational_alert_recipients",
                "status": "planned",
            }
        )

    if settings.agent_writeback_enabled and recommendations and (workbook_changed or force_report):
        actions.append(
            {
                "type": "writeback_recommendations",
                "priority": _priority_for_severity(max_severity),
                "target": settings.agent_actions_sheet_title,
                "status": "planned",
            }
        )

    if not actions:
        actions.append(
            {
                "type": "no_op",
                "priority": "Low",
                "target": "memory",
                "status": "planned",
            }
        )

    changed_text = "changed" if workbook_changed else "unchanged"
    summary = (
        f"Workbook {changed_text}; {len(findings)} finding(s) detected; "
        f"maximum severity is {max_severity}; {len(actions)} action(s) selected."
    )
    return {
        "mode": mode,
        "workbook_changed": workbook_changed,
        "workbook_hash": workbook_hash,
        "previous_workbook_hash": previous_workbook_hash,
        "max_severity": max_severity,
        "summary": summary,
        "findings": findings,
        "recommendations": recommendations,
        "actions": actions,
    }


def build_decision_notification(
    decision: Dict[str, Any],
    settings: Any,
    notification_type: str = "alert",
) -> Dict[str, str]:
    period = datetime.utcnow().strftime("%Y-%m-%d")
    label = "Escalation" if notification_type == "escalation" else "Operational Alert"
    subject = (
        f"Action Required: {label} - {settings.project_name} - {period}"
        if notification_type == "escalation"
        else f"{label} - {settings.project_name} - {period}"
    )
    lines = [
        f"Action Required: {label} - {settings.project_name}" if notification_type == "escalation" else f"{label}: {settings.project_name}",
        f"Date: {period}",
        "",
        "Context",
        decision.get("summary", "Autonomous decision policy selected an action."),
        "",
        "Facts and analysis",
    ]
    for index, finding in enumerate(decision.get("findings", []), start=1):
        lines.append(
            f"{index}. [{finding.get('severity', 'low').upper()}] "
            f"{finding.get('title', '')} - {finding.get('details', '')}"
        )

    lines.extend(["", "Recommended corrective actions with ownership and timelines"])
    for index, recommendation in enumerate(decision.get("recommendations", []), start=1):
        lines.append(
            f"{index}. [{recommendation.get('priority', 'Low')}] "
            f"{recommendation.get('responsible_unit', 'Unassigned')}: "
            f"{recommendation.get('recommendation', '')} "
            f"Due: {recommendation.get('due_date', 'Not set')}."
        )

    if notification_type == "escalation":
        lines.extend([
            "",
            "Clear ask and proposed next step",
            "Please confirm the accountable owner, recovery path, and first corrective action update by close of business within three working days.",
        ])
    lines.extend(["", "This notification was generated by the autonomous M&E intelligence cycle."])

    findings = decision.get("findings", [])
    recommendations = decision.get("recommendations", [])
    findings_rows = "\n".join(
        f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};font-weight:700;color:{BRAND_RED};">{html.escape(str(item.get('severity', 'low')).upper())}</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};">{html.escape(str(item.get('category', 'general')).replace('_', ' ').title())}</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};font-weight:700;color:{BRAND_DARK};">{html.escape(str(item.get('title', '')))}</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};color:{BRAND_MUTED};">{html.escape(str(item.get('details', '')))}</td>
        </tr>
        """
        for item in findings
    ) or (
        f'<tr><td colspan="4" style="padding:12px;border-bottom:1px solid {BRAND_LINE};">'
        "No findings were selected by the decision policy.</td></tr>"
    )
    recommendation_rows = "\n".join(
        f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};font-weight:700;">{html.escape(str(item.get('priority', 'Low')))}</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};">{html.escape(str(item.get('responsible_unit', 'Unassigned')))}</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};">{html.escape(str(item.get('recommendation', '')))}</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};white-space:nowrap;">{html.escape(str(item.get('due_date', 'Not set')))}</td>
        </tr>
        """
        for item in recommendations
    ) or (
        f'<tr><td colspan="4" style="padding:12px;border-bottom:1px solid {BRAND_LINE};">'
        "No recommendations were generated.</td></tr>"
    )
    ask_block = ""
    if notification_type == "escalation":
        ask_block = f"""
      <div style="display:block;margin:22px 0 0 0;padding:14px;border:1px solid {BRAND_LINE};background:#FFFFFF;">
        <div style="font-weight:700;color:{BRAND_DARK};">Clear ask and proposed next step</div>
        <p style="margin:6px 0 0 0;color:{BRAND_MUTED};">Please confirm the accountable owner, recovery path, and first corrective action update by close of business within three working days.</p>
      </div>
        """

    html_body = f"""
      <p style="margin:0 0 16px 0;">{html.escape(decision.get('summary', 'Autonomous decision policy selected an action.'))}</p>

      <div style="display:block;margin:18px 0;padding:16px;border-left:4px solid {BRAND_RED};background:{BRAND_LIGHT};">
        <div style="font-size:12px;color:{BRAND_RED};font-weight:700;text-transform:uppercase;letter-spacing:.06em;">{html.escape(label)} Trigger</div>
        <div style="font-size:28px;font-weight:800;color:{BRAND_DARK};margin-top:4px;">{html.escape(str(decision.get('max_severity', 'none')).upper())}</div>
        <div style="font-size:13px;color:{BRAND_MUTED};margin-top:4px;">{len(findings)} finding(s), {len(recommendations)} corrective action(s)</div>
      </div>

      <h2 style="font-size:16px;margin:22px 0 10px 0;color:{BRAND_BLUE};">Findings</h2>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid {BRAND_LINE};">
        <tr style="background:{BRAND_BLUE};color:#FFFFFF;">
          <th align="left" style="padding:10px 12px;">Severity</th>
          <th align="left" style="padding:10px 12px;">Area</th>
          <th align="left" style="padding:10px 12px;">Finding</th>
          <th align="left" style="padding:10px 12px;">Evidence</th>
        </tr>
        {findings_rows}
      </table>

      <h2 style="font-size:16px;margin:24px 0 10px 0;color:{BRAND_BLUE};">Corrective Action Plan</h2>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid {BRAND_LINE};">
        <tr style="background:{BRAND_BLUE};color:#FFFFFF;">
          <th align="left" style="padding:10px 12px;">Priority</th>
          <th align="left" style="padding:10px 12px;">Responsible Unit</th>
          <th align="left" style="padding:10px 12px;">Action</th>
          <th align="left" style="padding:10px 12px;">Due Date</th>
        </tr>
        {recommendation_rows}
      </table>

      {ask_block}

      <p style="margin-top:22px;color:{BRAND_MUTED};font-size:13px;">This notification was generated by the autonomous M&amp;E intelligence cycle.</p>
    """
    return {"subject": subject, "body": "\n".join(lines), "html_body": html_body}
