from typing import Dict, List, Any


def build_unified_project_state(normalized_sheets: List[Dict[str, Any]]) -> Dict[str, Any]:
    state = {
        "metadata": {},
        "activities": [],
        "outputs": [],
        "outcomes": [],
        "indicators": [],
        "risks": [],
        "budget": [],
        "workplan": [],
        "issues": [],
        "dependencies": [],
        "counts": {},
    }

    for sheet in normalized_sheets:
        if sheet["type"] == "metadata":
            if sheet["data"]:
                state["metadata"].update(sheet["data"][0])
        elif sheet["type"] == "gantt":
            for row in sheet["data"]:
                state["activities"].append(row)
                for dependency in row.get("dependencies", []):
                    state["dependencies"].append({
                        "activity_id": row["id"],
                        "dependency": dependency,
                    })
        elif sheet["type"] == "logframe":
            for row in sheet["data"]:
                if row.get("output"):
                    state["outputs"].append(row)
                if row.get("outcome"):
                    state["outcomes"].append(row)
        elif sheet["type"] == "kpi_tracker":
            state["indicators"].extend(sheet["data"])
        elif sheet["type"] == "risk_register":
            state["risks"].extend(sheet["data"])
        elif sheet["type"] == "budget":
            state["budget"].extend(sheet["data"])
        elif sheet["type"] == "workplan":
            state["workplan"].extend(sheet["data"])
        elif sheet["type"] == "issues_log":
            state["issues"].extend(sheet["data"])

    state["counts"] = {
        "activities": len(state["activities"]),
        "outputs": len(state["outputs"]),
        "outcomes": len(state["outcomes"]),
        "indicators": len(state["indicators"]),
        "risks": len(state["risks"]),
        "budget_lines": len(state["budget"]),
        "workplan_items": len(state["workplan"]),
        "issues": len(state["issues"]),
        "dependencies": len(state["dependencies"]),
    }

    return state
