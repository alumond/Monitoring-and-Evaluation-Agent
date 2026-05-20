import hashlib
import re
from typing import Any, Dict, List


def _normalize_key(key: str) -> str:
    key = re.sub(r"\s+", " ", key.strip().lower().replace("\n", " "))

    exact_mapping = {
        "task": "task",
        "activity": "task",
        "activity description": "task",
        "activity id": "activity_id",
        "start date": "start_date",
        "planned start": "start_date",
        "end date": "end_date",
        "planned end": "end_date",
        "actual start": "actual_start_date",
        "actual end": "actual_end_date",
        "status": "status",
        "assigned to": "assigned_to",
        "responsible": "assigned_to",
        "owner": "assigned_to",
        "dependency": "dependencies",
        "dependencies": "dependencies",
        "output": "output",
        "outcome": "outcome",
        "goal": "goal",
        "indicator": "indicator",
        "indicator description": "indicator",
        "baseline": "baseline",
        "target": "target",
        "annual target": "target",
        "ytd target": "target",
        "actual": "actual",
        "ytd actual": "actual",
        "progress": "progress",
        "progress %": "progress",
        "% complete": "progress",
        "achievement %": "progress",
        "trend": "trend",
        "risk": "risk",
        "risk description": "risk",
        "risk id": "risk_id",
        "risk level": "risk_level",
        "likelihood": "likelihood",
        "impact": "impact",
        "risk score": "severity",
        "mitigation": "mitigation",
        "mitigation strategy": "mitigation",
        "budget line": "line_item",
        "budget": "budget",
        "expenditure": "expenditure",
        "variance": "variance",
        "allocation": "allocation",
        "cost": "budget",
        "spent": "expenditure",
        "issue id": "issue_id",
        "issue description": "issue",
        "date raised": "date_raised",
        "raised by": "raised_by",
        "severity": "severity",
        "resolution action": "resolution_action",
        "target date": "target_date",
        "resolved date": "resolved_date",
        "category": "category",
    }
    if key in exact_mapping:
        return exact_mapping[key]

    if key.startswith("q") and "actual" in key:
        return "actual"
    if "indicator description" in key:
        return "indicator"
    if "activity description" in key:
        return "task"
    if "risk description" in key:
        return "risk"
    if "planned start" in key:
        return "start_date"
    if "planned end" in key:
        return "end_date"
    if "total budget" in key:
        return "budget"
    if "expenditure" in key or "spent" in key:
        return "expenditure"
    if "achievement" in key or "complete" in key:
        return "progress"
    if "risk score" in key:
        return "severity"
    if "mitigation" in key:
        return "mitigation"
    if "likelihood" in key:
        return "likelihood"
    if "impact" in key:
        return "impact"
    if "target" in key:
        return "target"
    if "actual" in key:
        return "actual"
    if "baseline" in key:
        return "baseline"

    return re.sub(r"[^a-z0-9]+", "_", key).strip("_")


def _is_quarter_key(key: str) -> bool:
    return bool(re.match(r"^q[1-4]_\d{4}$", key))


def _make_stable_id(prefix: str, seed: str) -> str:
    token = f"{prefix}:{seed}".encode("utf-8")
    return hashlib.sha1(token).hexdigest()[:16]


def _parse_number(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(',', '').strip())
    except ValueError:
        return 0.0


def _parse_list(value: Any) -> List[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    ignored = {"-", "\u2013", "\u2014", "n/a", "na", "none"}
    return [
        item.strip()
        for item in text.replace(';', ',').split(',')
        if item.strip() and item.strip().lower() not in ignored
    ]


def _normalize_row(headers: List[str], row: List[Any]) -> Dict[str, Any]:
    row_data = {}
    for name, value in zip(headers, row):
        normalized = _normalize_key(name)
        row_data[normalized] = value.strip() if isinstance(value, str) else value
    return row_data


def normalize_sheet(sheet: Dict[str, Any], sheet_type: str) -> Dict[str, Any]:
    headers = sheet.get("headers", [])
    rows = sheet.get("rows", [])
    if sheet_type == "metadata":
        metadata = {}
        for row in rows:
            if len(row) >= 2 and str(row[0]).strip():
                metadata[_normalize_key(str(row[0]))] = str(row[1]).strip()
        return {
            "title": sheet.get("title"),
            "type": sheet_type,
            "data": [metadata] if metadata else [],
        }

    normalized_rows = []
    for index, row in enumerate(rows, start=1):
        if not any(str(value).strip() for value in row):
            continue
        entry = _normalize_row(headers, row)
        if sheet_type == "gantt":
            task = str(entry.get("task", entry.get("activity", ""))).strip()
            entry["id"] = _make_stable_id("activity", task or str(index))
            entry["dependencies"] = _parse_list(entry.get("dependencies", ""))
            entry["start_date"] = entry.get("start_date")
            entry["end_date"] = entry.get("end_date")
            entry["status"] = str(entry.get("status", "")).strip()
        elif sheet_type == "logframe":
            level = str(entry.get("level", "")).strip().lower()
            description = str(entry.get("description", "")).strip()
            output_name = str(entry.get("output", "")).strip()
            outcome_name = str(entry.get("outcome", "")).strip()
            goal_name = str(entry.get("goal", "")).strip()
            if "output" in level and description:
                output_name = description
            elif "outcome" in level and description:
                outcome_name = description
            elif "goal" in level and description:
                goal_name = description
            entry["id"] = _make_stable_id("logframe", output_name or outcome_name or goal_name or str(index))
            entry["goal"] = goal_name
            entry["output"] = output_name
            entry["outcome"] = outcome_name
            entry["indicator"] = str(entry.get("indicator", "")).strip()
        elif sheet_type == "kpi_tracker":
            indicator_name = str(entry.get("indicator", "")).strip()
            entry["id"] = _make_stable_id("indicator", indicator_name or str(index))
            entry["baseline"] = _parse_number(entry.get("baseline", 0))
            entry["target"] = _parse_number(entry.get("target", 0))
            entry["actual"] = _parse_number(entry.get("actual", 0))
            entry["progress"] = _parse_number(entry.get("progress", 0))
        elif sheet_type == "risk_register":
            risk_name = str(entry.get("risk", "")).strip()
            entry["id"] = _make_stable_id("risk", risk_name or str(index))
            entry["likelihood"] = _parse_number(entry.get("likelihood", entry.get("probability", 0)))
            entry["impact"] = _parse_number(entry.get("impact", 0))
            entry["severity"] = round(entry["likelihood"] * entry["impact"], 2)
            entry["mitigation"] = str(entry.get("mitigation", "")).strip()
        elif sheet_type == "budget":
            line_item = str(entry.get("line_item", entry.get("description", ""))).strip()
            entry["id"] = _make_stable_id("budget", line_item or str(index))
            entry["budget"] = _parse_number(entry.get("budget", 0))
            entry["expenditure"] = _parse_number(entry.get("expenditure", entry.get("spent", 0)))
            entry["variance"] = _parse_number(entry.get("variance", entry.get("difference", 0)))
            entry["allocation"] = _parse_number(entry.get("allocation", 0))
        elif sheet_type == "workplan":
            activity = str(entry.get("task", "")).strip()
            entry["id"] = _make_stable_id("workplan", entry.get("activity_id") or activity or str(index))
            quarter_values = {
                key: str(value).strip()
                for key, value in entry.items()
                if _is_quarter_key(key) and str(value).strip()
            }
            entry["quarters"] = quarter_values
            entry["planned_quarter_count"] = len(quarter_values)
            entry["completed_quarter_count"] = sum(
                1 for value in quarter_values.values()
                if value.lower() in {"x", "done", "complete", "completed", "\u2713", "\u2714"}
            )
            entry["partial_quarter_count"] = sum(
                1 for value in quarter_values.values()
                if value.lower() in {"partial", "in progress", "\u25d1", "\u25d0"}
            )
        elif sheet_type == "issues_log":
            issue = str(entry.get("issue", "")).strip()
            entry["id"] = _make_stable_id("issue", entry.get("issue_id") or issue or str(index))
            entry["issue"] = issue
            entry["status"] = str(entry.get("status", "")).strip()
            entry["severity"] = str(entry.get("severity", "")).strip()
            entry["category"] = str(entry.get("category", "")).strip()
            entry["assigned_to"] = str(entry.get("assigned_to", "")).strip()
            entry["resolution_action"] = str(entry.get("resolution_action", "")).strip()
        else:
            entry["id"] = _make_stable_id("row", str(index))
        normalized_rows.append(entry)
    return {
        "title": sheet.get("title"),
        "type": sheet_type,
        "data": normalized_rows,
    }


def normalize_workbook(workbook: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from .classification import classify_sheet

    normalized = []
    for sheet in workbook:
        sheet_type = classify_sheet(sheet.get("headers", []))
        normalized.append(normalize_sheet(sheet, sheet_type))
    return normalized
