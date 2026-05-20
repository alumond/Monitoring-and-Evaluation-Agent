import re
from typing import Any, Dict, List, Optional

SheetType = str
LOGFRAME = "logframe"
GANTT = "gantt"
KPI_TRACKER = "kpi_tracker"
RISK_REGISTER = "risk_register"
BUDGET = "budget"
METADATA = "metadata"
WORKPLAN = "workplan"
ISSUES_LOG = "issues_log"
UNKNOWN = "unknown"


def normalize_header(header: str) -> str:
    return re.sub(r"\s+", " ", header.strip().lower().replace("\n", " "))


def _has(headers: List[str], *terms: str) -> bool:
    return any(term in header for header in headers for term in terms)


def classify_sheet(headers: List[str]) -> SheetType:
    normalized = [normalize_header(value) for value in headers]

    if _has(normalized, "project metadata"):
        return METADATA

    if (
        _has(normalized, "issue")
        and _has(normalized, "date raised", "target date", "resolved date")
        and _has(normalized, "resolution", "assigned to", "severity")
    ):
        return ISSUES_LOG

    if (
        _has(normalized, "activity")
        and _has(normalized, "output")
        and _has(normalized, "q1", "q2", "q3", "q4")
        and _has(normalized, "responsible", "budget line")
    ):
        return WORKPLAN

    if (
        _has(normalized, "means of verification", "assumption", "level")
        and _has(normalized, "indicator")
        and _has(normalized, "baseline", "target", "actual")
    ):
        return LOGFRAME

    if (
        _has(normalized, "activity", "task")
        and _has(normalized, "status")
        and _has(normalized, "start", "end", "dependency", "% complete")
    ):
        return GANTT

    if (
        _has(normalized, "indicator")
        and _has(normalized, "baseline", "target")
        and _has(normalized, "actual", "achievement", "progress", "trend")
    ):
        return KPI_TRACKER

    if (
        _has(normalized, "risk")
        and _has(normalized, "likelihood", "probability")
        and _has(normalized, "impact", "score", "mitigation")
    ):
        return RISK_REGISTER

    if (
        _has(normalized, "budget")
        and _has(normalized, "expenditure", "spent", "utilised", "utilized", "burn rate", "remaining")
    ):
        return BUDGET

    return UNKNOWN


def classify_workbook(workbook: List[Dict[str, List[str]]]) -> List[Dict[str, Any]]:
    classified = []
    for sheet in workbook:
        sheet_type = classify_sheet(sheet.get("headers", []))
        classified.append({
            "title": sheet["title"],
            "type": sheet_type,
            "headers": sheet["headers"],
            "rows": sheet["rows"],
        })
    return classified


def find_activity_tracker(classified_sheets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates = [sheet for sheet in classified_sheets if sheet["type"] == GANTT]
    if candidates:
        return candidates[0]
    return None
