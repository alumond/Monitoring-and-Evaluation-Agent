import html
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple


BRAND_BLUE = "#004C86"
BRAND_RED = "#FF1F1F"
BRAND_DARK = "#24313D"
BRAND_MUTED = "#647282"
BRAND_LINE = "#D9E1EA"
BRAND_LIGHT = "#F5F8FB"


def clean_indicator_label(indicator: Any) -> str:
    label = str(indicator or "").strip()
    label = re.sub(r"^#\s*", "Number of ", label)
    label = re.sub(r"^%\s*", "Percentage of ", label)
    return label


def identify_missed_targets(analytics: Dict[str, Any], threshold_percent: float) -> List[Dict[str, Any]]:
    missed = []
    for indicator in analytics.get("kpi", {}).get("performance", []):
        target = float(indicator.get("target", 0) or 0)
        actual = float(indicator.get("actual", 0) or 0)
        perf = float(indicator.get("performance_percent", 0) or 0)
        if target > 0 and perf < threshold_percent:
            missed.append(
                {
                    "indicator_id": indicator.get("indicator_id"),
                    "indicator": clean_indicator_label(indicator.get("indicator")),
                    "baseline": indicator.get("baseline"),
                    "target": target,
                    "actual": actual,
                    "performance_percent": perf,
                    "target_gap": round(target - actual, 2),
                    "variance_percent": round(perf - 100.0, 2),
                    "missed_by_percent": round(threshold_percent - perf, 2),
                }
            )
    return missed


def infer_root_causes(analytics: Dict[str, Any]) -> List[str]:
    causes = []
    if analytics.get("schedule", {}).get("overdue_count", 0) > 0:
        causes.append("Implementation delays and overdue activities")
    if analytics.get("dependency", {}).get("blocked_activity_count", 0) > 0:
        causes.append("Dependency bottlenecks blocking progress")
    if analytics.get("risk", {}).get("high_risk_count", 0) > 0:
        causes.append("High-severity risk exposure")
    if analytics.get("budget", {}).get("utilization_percent", 0.0) < 70.0:
        causes.append("Budget constraints or underutilized resources")
    if not causes:
        causes.append("No clear root cause inferred; validate operational and data inputs.")
    return causes


def recommend_corrective_actions(root_causes: List[str]) -> List[str]:
    actions = []
    if any("delay" in cause.lower() or "overdue" in cause.lower() for cause in root_causes):
        actions.append("Reprioritize overdue activities and assign resources to critical path tasks.")
    if any("dependency" in cause.lower() for cause in root_causes):
        actions.append("Resolve blocked dependencies and accelerate coordination across teams.")
    if any("risk" in cause.lower() for cause in root_causes):
        actions.append("Escalate high-severity risks and activate mitigation plans immediately.")
    if any("budget" in cause.lower() for cause in root_causes):
        actions.append("Review budget allocations and reallocate funds to under-resourced priority activities.")
    if not actions:
        actions.append("Validate the data and convene a rapid review to confirm root cause assumptions.")
    return actions


def infer_potential_impact(item: Dict[str, Any], root_causes: List[str]) -> str:
    gap = float(item.get("target_gap", 0) or 0)
    indicator = item.get("indicator", "the affected indicator")
    if any("dependency" in cause.lower() for cause in root_causes):
        return f"Continued dependency blockage may keep {indicator} below target and delay linked outputs."
    if any("delay" in cause.lower() or "overdue" in cause.lower() for cause in root_causes):
        return f"Implementation slippage may widen the {gap:,.2f} unit gap and weaken delivery confidence."
    if any("risk" in cause.lower() for cause in root_causes):
        return f"Unmitigated risk exposure may reduce the likelihood of recovering the {gap:,.2f} unit gap this cycle."
    if any("budget" in cause.lower() for cause in root_causes):
        return f"Resource misalignment may constrain recovery against the {gap:,.2f} unit gap."
    return f"The current {gap:,.2f} unit gap requires validation and a focused recovery plan before the next review."


def _format_action_plan(corrective_actions: List[str]) -> List[str]:
    owners = ["Program Manager", "M&E Lead", "Finance/Operations Lead", "Country Director"]
    timelines = ["within 3 working days", "within 5 working days", "within 7 working days", "at the next management review"]
    plan = []
    for index, action in enumerate(corrective_actions):
        owner = owners[min(index, len(owners) - 1)]
        timeline = timelines[min(index, len(timelines) - 1)]
        plan.append(f"{owner}: {action} Timeline: {timeline}.")
    return plan


def build_escalation_message(
    missed_targets: List[Dict[str, Any]],
    root_causes: List[str],
    corrective_actions: List[str],
    settings: Any,
) -> Tuple[str, str, str]:
    period = datetime.utcnow().strftime("%Y-%m-%d")
    subject = settings.escalation_subject_format.format(
        project_name=settings.project_name,
        period=period,
        issue="Missed KPI Targets",
    )

    opening = settings.escalation_message_template.format(
        project_name=settings.project_name,
        period=period,
    )
    root_cause_text = "; ".join(root_causes)
    action_plan = _format_action_plan(corrective_actions)
    lines = [
        f"Action Required: KPI Target Breach - {settings.project_name}",
        f"Date: {period}",
        "",
        "Context",
        opening,
        "",
        "Facts and analysis",
    ]
    for index, item in enumerate(missed_targets, start=1):
        lines.append(
            f"{index}. {item['indicator']}: Actual Value {item['actual']:,.2f}; "
            f"Performance vs Target {item['performance_percent']:.1f}% achievement against "
            f"{item['target']:,.2f} target; variance {item['variance_percent']:.1f}% "
            f"({item['target_gap']:,.2f} unit gap). Likely root cause: {root_cause_text}. "
            f"Potential impact: {infer_potential_impact(item, root_causes)}"
        )

    lines.extend(["", "Likely root causes"])
    for index, cause in enumerate(root_causes, start=1):
        lines.append(f"{index}. {cause}")

    lines.extend(["", "Recommended corrective actions with ownership and timelines"])
    for index, action in enumerate(action_plan, start=1):
        lines.append(f"{index}. {action}")

    lines.extend([
        "",
        "Clear ask and proposed next step",
        "Please confirm the recovery owner, revised delivery path, and first corrective action update by close of business within three working days.",
        "",
        "Regards,",
        "Monitoring & Evaluation Intelligence Team",
    ])
    body = "\n".join(lines)

    missed_rows = "\n".join(
        f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};">{html.escape(str(item['indicator']))}</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};text-align:right;">{item['actual']:,.2f}</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};text-align:right;">{item['target']:,.2f}</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};text-align:right;color:{BRAND_RED};font-weight:700;">{item['performance_percent']:.1f}%</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};text-align:right;">{item['variance_percent']:.1f}%</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};text-align:right;">{item['target_gap']:,.2f}</td>
          <td style="padding:10px 12px;border-bottom:1px solid {BRAND_LINE};color:{BRAND_MUTED};">{html.escape(infer_potential_impact(item, root_causes))}</td>
        </tr>
        """
        for item in missed_targets
    )
    root_cause_items = "".join(f"<li>{html.escape(cause)}</li>" for cause in root_causes)
    action_items = "".join(f"<li>{html.escape(action)}</li>" for action in action_plan)

    html_body = f"""
      <p style="margin:0 0 16px 0;">{html.escape(opening)}</p>

      <div style="display:block;margin:18px 0;padding:16px;border-left:4px solid {BRAND_RED};background:{BRAND_LIGHT};">
        <div style="font-size:12px;color:{BRAND_RED};font-weight:700;text-transform:uppercase;letter-spacing:.06em;">Escalation Trigger</div>
        <div style="font-size:28px;font-weight:800;color:{BRAND_DARK};margin-top:4px;">{len(missed_targets)} KPI target breach{'es' if len(missed_targets) != 1 else ''}</div>
        <div style="font-size:13px;color:{BRAND_MUTED};margin-top:4px;">Threshold: {settings.escalation_kpi_threshold:.1f}% performance</div>
      </div>

      <h2 style="font-size:16px;margin:22px 0 10px 0;color:{BRAND_BLUE};">Missed KPI Targets</h2>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid {BRAND_LINE};">
        <tr style="background:{BRAND_BLUE};color:#FFFFFF;">
          <th align="left" style="padding:10px 12px;">Indicator</th>
          <th align="right" style="padding:10px 12px;">Actual</th>
          <th align="right" style="padding:10px 12px;">Target</th>
          <th align="right" style="padding:10px 12px;">Achievement</th>
          <th align="right" style="padding:10px 12px;">Variance</th>
          <th align="right" style="padding:10px 12px;">Target Gap</th>
          <th align="left" style="padding:10px 12px;">Potential Impact</th>
        </tr>
        {missed_rows}
      </table>

      <h2 style="font-size:16px;margin:24px 0 8px 0;color:{BRAND_BLUE};">Likely Root Causes</h2>
      <ul style="margin-top:8px;padding-left:22px;">{root_cause_items}</ul>

      <h2 style="font-size:16px;margin:24px 0 8px 0;color:{BRAND_BLUE};">Recommended Corrective Actions</h2>
      <ul style="margin-top:8px;padding-left:22px;">{action_items}</ul>

      <div style="display:block;margin:22px 0 0 0;padding:14px;border:1px solid {BRAND_LINE};background:#FFFFFF;">
        <div style="font-weight:700;color:{BRAND_DARK};">Clear ask and proposed next step</div>
        <p style="margin:6px 0 0 0;color:{BRAND_MUTED};">Please confirm the recovery owner, revised delivery path, and first corrective action update by close of business within three working days.</p>
      </div>

      <p style="margin-top:22px;color:{BRAND_MUTED};font-size:13px;">Regards,<br/>Monitoring &amp; Evaluation Intelligence Team</p>
    """
    return subject, body, html_body


def assess_escalation(analytics: Dict[str, Any], threshold_percent: float) -> Dict[str, Any]:
    missed_targets = identify_missed_targets(analytics, threshold_percent)
    root_causes = infer_root_causes(analytics)
    corrective_actions = recommend_corrective_actions(root_causes)
    return {
        "should_escalate": bool(missed_targets),
        "missed_targets": missed_targets,
        "root_causes": root_causes,
        "corrective_actions": corrective_actions,
    }
