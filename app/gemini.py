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
            "You are a senior Monitoring & Evaluation strategist with 18 years of experience presenting to donors, "
            "Country Directors, and executive boards. Produce an exceptionally polished, high-level report with the "
            "clarity, restraint, and visual discipline of a premium executive briefing. The tone must be confident, "
            "mature, diplomatic, and human, never robotic or generic.\n\n"
            "Use only the structured analytics and high-level project state provided below. Do not invent spreadsheet "
            "rows, indicators, dates, targets, budgets, risks, owners, or donor requirements. Where evidence is limited, "
            "say so professionally and frame the validation required.\n\n"
            "Report excellence standards:\n"
            "- Overall feel: premium, scannable, donor-ready, with generous white space, clear visual hierarchy, "
            "strategic emphasis, and short paragraphs.\n"
            "- Analytical depth: focus on causal interpretation, risk explanation, cross-sheet impact, operational "
            "consequences, and management decisions, not descriptive narration.\n"
            "- Design and readability: use bold subheadings, concise action bullets, and Markdown tables where they "
            "make performance, risk, budget, or issue data easier to scan.\n"
            "- Indicators: always present Actual Value first, immediately followed by Performance vs Target, including "
            "percentage achievement. Apply clear status language: Green/on track, Amber/at risk, Red/off track.\n"
            "- Risks and critical issues: highlight each major risk or bottleneck in a distinct boxed call-out using "
            "Markdown blockquotes starting with > or a compact bordered table. Each call-out must name the risk, "
            "evidence, implication, and required action.\n"
            "- Recommendations: make them operational, prioritized, mapped to issues or causes, and specific about "
            "ownership and timelines when the source data supports it.\n\n"
            "Tone guardrails: write like an experienced M&E lead speaking directly to senior management and donors. "
            "Vary sentence length. Use subtle urgency when performance is slipping. Avoid filler phrases and "
            "AI-sounding language.\n\n"
            "Formatting rules:\n"
            "- Use the exact section titles as standalone lines, in the exact order requested. Do not number them.\n"
            "- Under each section, include one short framing paragraph and 3 to 5 high-value bullets where useful.\n"
            "- Prefer labelled bullets such as Finding:, Evidence:, Implication:, Action:, Owner:, and Timeline:.\n"
            "- Keep the report concise enough for an executive reader while retaining the evidence needed for action."
        )
        summary = {
            "project_state": project_state.get("counts", {}),
            "project_metadata": project_state.get("metadata", {}),
            "analytics": analytics,
        }
        return (
            f"{instructions}\n\n"
            f"Structured summary:\n{json.dumps(summary, indent=2)}\n\n"
            "Required structure, exact order:\n"
            "Executive Summary\n"
            "Project Metadata & Governance Context\n"
            "Activity Implementation Analysis\n"
            "Workplan Analysis\n"
            "Logframe Performance Analysis\n"
            "Indicator Performance Analysis\n"
            "Risk & Bottleneck Analysis\n"
            "Issues Log Analysis\n"
            "Budget & Resource Utilization\n"
            "Data Quality Assessment\n"
            "Dependency & Impact Analysis\n"
            "Forecasting & Predictive Insights\n"
            "Recommendations & Corrective Action Plan\n\n"
            "Treat metadata, workplan, logframe, indicator, risk, issues, budget, data quality, dependencies, forecasting, "
            "and corrective action as dedicated analysis modules wherever the analytics provide evidence."
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
