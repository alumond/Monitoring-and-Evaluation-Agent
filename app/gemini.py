import json
import time
from typing import Any, Dict
import requests
from .config import get_settings


class GeminiClient:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.api_url = self.settings.gemini_api_url
        self.api_key = self.settings.gemini_api_key

    def _build_prompt(self, analytics: Dict[str, Any], project_state: Dict[str, Any]) -> str:
        instructions = (
            "You are an enterprise Monitoring & Evaluation intelligence engine. "
            "Using only the provided structured analytics and high-level project state, generate a donor-grade narrative report. "
            "Do not invent raw spreadsheet rows. Focus on causal interpretation, risk explanation, cross-sheet impact, and operational recommendations. "
            "Use polished executive prose, but prefer structured listing where it improves scanability. "
            "Within each section, use short labelled bullets such as Finding:, Evidence:, Implication:, and Action:. "
            "Avoid dense paragraphs, avoid Markdown decoration such as # headings or asterisk emphasis, and do not use markdown tables."
        )
        summary = {
            "project_state": project_state.get("counts", {}),
            "project_metadata": project_state.get("metadata", {}),
            "analytics": analytics,
        }
        return (
            f"{instructions}\n\n"
            f"Structured summary:\n{json.dumps(summary, indent=2)}\n\n"
            "Produce the report with these exact section titles: Executive Summary; Project Metadata & Governance Context; "
            "Activity Implementation Analysis; Workplan Analysis; Logframe Performance Analysis; Indicator Performance Analysis; "
            "Risk & Bottleneck Analysis; Issues Log Analysis; Budget & Resource Utilization; Data Quality Assessment; "
            "Dependency & Impact Analysis; Forecasting & Predictive Insights; Recommendations & Corrective Action Plan. "
            "Treat Metadata, Workplan, and Issues Log as dedicated analysis modules where the analytics provide evidence. "
            "Keep each section concise: one short framing paragraph followed by 3 to 5 labelled bullets where possible."
        )

    def generate_report_text(self, analytics: Dict[str, Any], project_state: Dict[str, Any]) -> str:
        prompt = self._build_prompt(analytics, project_state)
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                    ],
                },
            ],
        }
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        response = None
        for attempt in range(3):
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=120)
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
            if attempt < 2:
                time.sleep(2 ** attempt)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "candidates" in data:
            parts = data["candidates"][0].get("content", {}).get("parts", [])
            return "\n".join(str(part.get("text", "")) for part in parts).strip()
        if isinstance(data, dict) and "output" in data:
            return str(data["output"])
        if isinstance(data, dict) and "choices" in data:
            choice = data["choices"][0]
            return str(choice.get("message", {}).get("content", ""))
        return str(data)
