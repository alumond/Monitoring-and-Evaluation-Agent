from datetime import datetime
from typing import Any, Dict, List


def _parse_date(value: Any):
    if not value:
        return None
    text = str(value).strip()
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y", "%d %b %Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _safe_number(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return 0.0


def _status_counts(rows: List[Dict[str, Any]], key: str = "status") -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        status = str(row.get(key, "")).strip() or "Unspecified"
        counts[status] = counts.get(status, 0) + 1
    return counts


def _severity_rank(value: Any) -> int:
    text = str(value).strip().lower()
    if text in {"critical", "very high"}:
        return 5
    if text == "high":
        return 4
    if text == "medium":
        return 3
    if text == "low":
        return 2
    if text == "minor":
        return 1
    number = _safe_number(value)
    return int(number) if number else 0


def compute_schedule_variance(activities: List[Dict[str, Any]]) -> Dict[str, Any]:
    variances = []
    today = datetime.utcnow().date()
    for activity in activities:
        start = _parse_date(activity.get("start_date"))
        end = _parse_date(activity.get("end_date"))
        if not start or not end:
            continue
        elapsed = (end - start).days
        expected = elapsed
        variances.append({
            "activity_id": activity["id"],
            "task": activity.get("task", ""),
            "planned_days": expected,
            "is_overdue": end < today and str(activity.get("status", "")).strip().lower() not in {"complete", "completed", "closed", "done"},
            "status": activity.get("status", ""),
        })
    overdue_count = sum(1 for item in variances if item["is_overdue"])
    return {
        "activity_count": len(activities),
        "schedule_records": variances,
        "overdue_count": overdue_count,
        "status_counts": _status_counts(activities),
    }


def compute_kpi_performance(indicators: List[Dict[str, Any]]) -> Dict[str, Any]:
    results = []
    for indicator in indicators:
        baseline = _safe_number(indicator.get("baseline"))
        target = _safe_number(indicator.get("target"))
        actual = _safe_number(indicator.get("actual"))
        progress = _safe_number(indicator.get("progress"))
        performance = 0.0
        if target:
            performance = min(100.0, (actual / target) * 100.0)
        results.append({
            "indicator_id": indicator["id"],
            "indicator": indicator.get("indicator", ""),
            "baseline": baseline,
            "target": target,
            "actual": actual,
            "progress": progress,
            "performance_percent": round(performance, 2),
        })
    on_track = sum(1 for item in results if item["performance_percent"] >= 100.0)
    return {
        "indicator_count": len(indicators),
        "performance": results,
        "on_track_count": on_track,
    }


def compute_activity_completion(activities: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(activities)
    completed = sum(1 for activity in activities if str(activity.get("status", "")).strip().lower() in {"complete", "completed", "done", "closed"})
    percent_complete = round((completed / total) * 100.0, 2) if total else 0.0
    return {
        "total_activities": total,
        "completed_activities": completed,
        "remaining_activities": max(total - completed, 0),
        "percent_complete": percent_complete,
    }


def compute_risk_severity(risks: List[Dict[str, Any]]) -> Dict[str, Any]:
    scored = []
    for risk in risks:
        likelihood = _safe_number(risk.get("likelihood"))
        impact = _safe_number(risk.get("impact"))
        severity = _safe_number(risk.get("severity")) or round(likelihood * impact, 2)
        scored.append({
            "risk_id": risk["id"],
            "risk": risk.get("risk", ""),
            "likelihood": likelihood,
            "impact": impact,
            "severity": severity,
            "mitigation": risk.get("mitigation", ""),
        })
    high_risks = [item for item in scored if item["severity"] >= 7.0]
    return {
        "risk_count": len(risks),
        "risk_records": scored,
        "high_risk_count": len(high_risks),
        "severity_counts": {
            "High": sum(1 for item in scored if item["severity"] >= 7.0),
            "Medium": sum(1 for item in scored if 4.0 <= item["severity"] < 7.0),
            "Low": sum(1 for item in scored if 0 < item["severity"] < 4.0),
        },
    }


def compute_dependency_bottlenecks(activities: List[Dict[str, Any]], dependencies: List[Dict[str, Any]]) -> Dict[str, Any]:
    dependent_counts = {}
    for dependency in dependencies:
        target = dependency.get("dependency")
        if not target:
            continue
        dependent_counts[target] = dependent_counts.get(target, 0) + 1
    bottlenecks = sorted(
        [{"dependency": dep, "count": count} for dep, count in dependent_counts.items()],
        key=lambda item: item["count"],
        reverse=True,
    )[:10]
    blocked = [activity for activity in activities if str(activity.get("status", "")).strip().lower() in {"blocked", "on hold", "delayed"}]
    return {
        "bottlenecks": bottlenecks,
        "blocked_activity_count": len(blocked),
    }


def compute_budget_utilization(budget_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_budget = sum(_safe_number(item.get("budget")) for item in budget_items)
    total_expenditure = sum(_safe_number(item.get("expenditure")) for item in budget_items)
    utilization_percent = round((total_expenditure / total_budget) * 100.0, 2) if total_budget else 0.0
    return {
        "budget_line_count": len(budget_items),
        "total_budget": total_budget,
        "total_expenditure": total_expenditure,
        "remaining_budget": total_budget - total_expenditure,
        "utilization_percent": utilization_percent,
    }


def compute_workplan_analysis(workplan_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    quarter_counts: Dict[str, int] = {}
    responsible_counts: Dict[str, int] = {}
    budget_line_counts: Dict[str, int] = {}
    total_markers = 0
    completed_markers = 0
    partial_markers = 0

    for item in workplan_items:
        for quarter in item.get("quarters", {}):
            quarter_counts[quarter] = quarter_counts.get(quarter, 0) + 1
            total_markers += 1
        completed_markers += int(item.get("completed_quarter_count", 0))
        partial_markers += int(item.get("partial_quarter_count", 0))
        responsible = str(item.get("assigned_to", "")).strip() or "Unassigned"
        responsible_counts[responsible] = responsible_counts.get(responsible, 0) + 1
        budget_line = str(item.get("line_item", "")).strip() or "Unmapped"
        budget_line_counts[budget_line] = budget_line_counts.get(budget_line, 0) + 1

    return {
        "workplan_item_count": len(workplan_items),
        "quarter_counts": dict(sorted(quarter_counts.items())),
        "responsible_counts": responsible_counts,
        "budget_line_counts": budget_line_counts,
        "planned_quarter_markers": total_markers,
        "completed_quarter_markers": completed_markers,
        "partial_quarter_markers": partial_markers,
        "quarter_completion_percent": round((completed_markers / total_markers) * 100.0, 2) if total_markers else 0.0,
    }


def compute_issues_analysis(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    status_counts = _status_counts(issues)
    severity_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}
    open_issues = []
    high_open_issues = []

    for issue in issues:
        severity = str(issue.get("severity", "")).strip() or "Unspecified"
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        category = str(issue.get("category", "")).strip() or "Uncategorized"
        category_counts[category] = category_counts.get(category, 0) + 1
        status = str(issue.get("status", "")).strip().lower()
        if status not in {"resolved", "closed", "complete", "completed"}:
            open_issues.append(issue)
            if _severity_rank(issue.get("severity")) >= 4:
                high_open_issues.append(issue)

    return {
        "issue_count": len(issues),
        "open_issue_count": len(open_issues),
        "resolved_issue_count": status_counts.get("Resolved", 0),
        "high_open_issue_count": len(high_open_issues),
        "status_counts": status_counts,
        "severity_counts": severity_counts,
        "category_counts": category_counts,
        "open_issues": [
            {
                "issue_id": item.get("issue_id", item.get("id")),
                "issue": item.get("issue", ""),
                "severity": item.get("severity", ""),
                "status": item.get("status", ""),
                "target_date": item.get("target_date", ""),
            }
            for item in open_issues[:10]
        ],
    }


def summarize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "project_name": metadata.get("project_name", ""),
        "project_code": metadata.get("project_code", ""),
        "implementing_partner": metadata.get("implementing_partner", ""),
        "donor": metadata.get("donor", ""),
        "reporting_period": metadata.get("reporting_period", metadata.get("period", "")),
        "country": metadata.get("country", ""),
        "currency": metadata.get("currency", ""),
    }


def identify_data_quality_issues(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues = []
    if not state["activities"]:
        issues.append({"type": "missing_sheet", "message": "No activity tracker sheet was found."})
    if not state["indicators"]:
        issues.append({"type": "missing_sheet", "message": "No KPI tracker sheet was found."})
    if not state.get("workplan"):
        issues.append({"type": "missing_sheet", "message": "No workplan sheet was found."})
    if not state.get("issues"):
        issues.append({"type": "missing_sheet", "message": "No issues log sheet was found."})
    for activity in state["activities"]:
        if not activity.get("task"):
            issues.append({"type": "missing_value", "message": f"Activity row {activity['id']} has no task name."})
    return issues


def compute_velocity_trend(activities: List[Dict[str, Any]]) -> Dict[str, Any]:
    completed = [activity for activity in activities if str(activity.get("status", "")).strip().lower() in {"complete", "completed", "done", "closed"}]
    trend = "stable"
    if len(completed) / len(activities) if activities else 0 > 0.5:
        trend = "accelerating"
    elif len(completed) / len(activities) if activities else 0 < 0.2:
        trend = "lagging"
    return {
        "completed_count": len(completed),
        "velocity_ratio": round((len(completed) / len(activities)) * 100.0, 2) if activities else 0.0,
        "trend": trend,
    }


def compute_project_analytics(state: Dict[str, Any]) -> Dict[str, Any]:
    schedule = compute_schedule_variance(state.get("activities", []))
    kpi = compute_kpi_performance(state.get("indicators", []))
    completion = compute_activity_completion(state.get("activities", []))
    risk = compute_risk_severity(state.get("risks", []))
    dependency = compute_dependency_bottlenecks(state.get("activities", []), state.get("dependencies", []))
    budget = compute_budget_utilization(state.get("budget", []))
    workplan = compute_workplan_analysis(state.get("workplan", []))
    issues = compute_issues_analysis(state.get("issues", []))
    metadata = summarize_metadata(state.get("metadata", {}))
    quality = identify_data_quality_issues(state)
    velocity = compute_velocity_trend(state.get("activities", []))

    return {
        "metadata": metadata,
        "schedule": schedule,
        "kpi": kpi,
        "completion": completion,
        "risk": risk,
        "dependency": dependency,
        "budget": budget,
        "workplan": workplan,
        "issues": issues,
        "data_quality": quality,
        "velocity": velocity,
    }
