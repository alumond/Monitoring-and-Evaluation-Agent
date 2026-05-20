import json
from datetime import date
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import select
from .config import get_settings
from .models import (
    AgentAction,
    AgentFinding,
    AgentRecommendation,
    AgentRun,
    Base,
    EscalationEvent,
    ReportLog,
    TriggerEvent,
    WorkbookSnapshot,
)


class AuditService:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        connect_args = {"check_same_thread": False} if self.settings.log_db_url.startswith("sqlite://") else {}
        self.engine = create_engine(self.settings.log_db_url, connect_args=connect_args, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def init_db(self) -> None:
        Base.metadata.create_all(bind=self.engine)

    def _serialize(self, payload: Any) -> str:
        if payload is None:
            return ""
        return json.dumps(payload, default=str, indent=2)

    def _deserialize(self, payload: Optional[str]) -> Any:
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload

    def log_trigger(self, sheet_title: str, changed_column: str, old_value: str, new_value: str, event_timestamp: str, payload: Any) -> int:
        with self.SessionLocal() as session:
            event = TriggerEvent(
                sheet_title=sheet_title,
                changed_column=changed_column,
                old_value=old_value,
                new_value=new_value,
                event_timestamp=event_timestamp,
                payload_snapshot=self._serialize(payload),
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return event.id

    def log_report(self, report_path: str, email_status: str, analytics: Any, workbook: Any, narrative: str) -> int:
        with self.SessionLocal() as session:
            report = ReportLog(
                report_path=report_path,
                email_status=email_status,
                analytics_snapshot=self._serialize(analytics),
                workbook_snapshot=self._serialize(workbook),
                narrative_snippet=(narrative or "")[:4000],
            )
            session.add(report)
            session.commit()
            session.refresh(report)
            return report.id

    def log_escalation(
        self,
        escalation_type: str,
        reason: str,
        recipients: list,
        details: Any = None,
    ) -> int:
        with self.SessionLocal() as session:
            escalation = EscalationEvent(
                escalation_type=escalation_type,
                reason=reason,
                recipients=",".join(recipients),
                details=self._serialize(details),
            )
            session.add(escalation)
            session.commit()
            session.refresh(escalation)
            return escalation.id

    def get_latest_agent_memory(self) -> Optional[Dict[str, Any]]:
        with self.SessionLocal() as session:
            run = session.execute(
                select(AgentRun)
                .where(AgentRun.status == "completed")
                .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
                .limit(1)
            ).scalars().first()
            if not run:
                return None

            snapshot = session.execute(
                select(WorkbookSnapshot)
                .where(WorkbookSnapshot.agent_run_id == run.id)
                .order_by(WorkbookSnapshot.id.desc())
                .limit(1)
            ).scalars().first()

            findings = session.execute(
                select(AgentFinding)
                .where(AgentFinding.agent_run_id == run.id)
                .order_by(AgentFinding.id.asc())
            ).scalars().all()

            recommendations = session.execute(
                select(AgentRecommendation)
                .where(AgentRecommendation.agent_run_id == run.id)
                .order_by(AgentRecommendation.id.asc())
            ).scalars().all()

            return {
                "id": run.id,
                "mode": run.mode,
                "created_at": run.created_at,
                "workbook_hash": run.workbook_hash,
                "analytics_hash": run.analytics_hash,
                "analytics": self._deserialize(run.analytics_snapshot),
                "state": self._deserialize(run.state_snapshot),
                "decision_summary": run.decision_summary,
                "max_severity": run.max_severity,
                "snapshot": {
                    "workbook_hash": snapshot.workbook_hash if snapshot else run.workbook_hash,
                    "analytics_hash": snapshot.analytics_hash if snapshot else run.analytics_hash,
                    "analytics": self._deserialize(snapshot.analytics_snapshot) if snapshot else self._deserialize(run.analytics_snapshot),
                },
                "findings": [
                    {
                        "finding_key": item.finding_key,
                        "category": item.category,
                        "severity": item.severity,
                        "title": item.title,
                        "details": item.details,
                        "status": item.status,
                    }
                    for item in findings
                ],
                "recommendations": [
                    {
                        "finding_key": item.finding_key,
                        "priority": item.priority,
                        "responsible_unit": item.responsible_unit,
                        "recommendation": item.recommendation,
                        "due_date": item.due_date,
                        "status": item.status,
                    }
                    for item in recommendations
                ],
            }

    def get_overdue_open_recommendations(self, today: Optional[date] = None) -> List[Dict[str, Any]]:
        today = today or date.today()
        with self.SessionLocal() as session:
            recommendations = session.execute(
                select(AgentRecommendation)
                .where(AgentRecommendation.status == "open")
                .order_by(AgentRecommendation.due_date.asc(), AgentRecommendation.id.asc())
            ).scalars().all()

            overdue = []
            for item in recommendations:
                if not item.due_date:
                    continue
                try:
                    due_date = date.fromisoformat(str(item.due_date)[:10])
                except ValueError:
                    continue
                if due_date > today:
                    continue
                overdue.append(
                    {
                        "id": item.id,
                        "finding_key": item.finding_key,
                        "priority": item.priority,
                        "responsible_unit": item.responsible_unit,
                        "recommendation": item.recommendation,
                        "due_date": item.due_date,
                        "status": item.status,
                    }
                )
            return overdue

    def log_agent_run(
        self,
        mode: str,
        status: str,
        trigger_source: str = "",
        trigger_context: Any = None,
        workbook_hash: str = "",
        analytics_hash: str = "",
        decision: Optional[Dict[str, Any]] = None,
        action_results: Optional[List[Dict[str, Any]]] = None,
        analytics: Any = None,
        workbook: Any = None,
        state: Any = None,
        error_message: str = "",
    ) -> int:
        decision = decision or {}
        findings = decision.get("findings", [])
        recommendations = decision.get("recommendations", [])
        actions = action_results if action_results is not None else decision.get("actions", [])

        with self.SessionLocal() as session:
            run = AgentRun(
                mode=mode,
                status=status,
                trigger_source=trigger_source,
                workbook_hash=workbook_hash,
                analytics_hash=analytics_hash,
                max_severity=decision.get("max_severity", ""),
                decision_summary=decision.get("summary", ""),
                trigger_context=self._serialize(trigger_context),
                analytics_snapshot=self._serialize(analytics),
                state_snapshot=self._serialize(state),
                error_message=error_message,
            )
            session.add(run)
            session.flush()

            if workbook is not None or analytics is not None:
                session.add(
                    WorkbookSnapshot(
                        agent_run_id=run.id,
                        workbook_hash=workbook_hash,
                        analytics_hash=analytics_hash,
                        workbook_snapshot=self._serialize(workbook),
                        analytics_snapshot=self._serialize(analytics),
                    )
                )

            for item in findings:
                session.add(
                    AgentFinding(
                        agent_run_id=run.id,
                        finding_key=item.get("finding_key", ""),
                        category=item.get("category", "general"),
                        severity=item.get("severity", "low"),
                        title=item.get("title", ""),
                        details=item.get("details", ""),
                        evidence_snapshot=self._serialize(item.get("evidence")),
                        status=item.get("status", "open"),
                    )
                )

            for item in recommendations:
                session.add(
                    AgentRecommendation(
                        agent_run_id=run.id,
                        finding_key=item.get("finding_key", ""),
                        priority=item.get("priority", "Low"),
                        responsible_unit=item.get("responsible_unit", ""),
                        recommendation=item.get("recommendation", ""),
                        due_date=item.get("due_date", ""),
                        status=item.get("status", "open"),
                    )
                )

            for item in actions:
                session.add(
                    AgentAction(
                        agent_run_id=run.id,
                        action_type=item.get("type", item.get("action_type", "")),
                        priority=item.get("priority", ""),
                        target=item.get("target", ""),
                        status=item.get("status", "planned"),
                        details=self._serialize(item),
                    )
                )

            session.commit()
            session.refresh(run)
            return run.id
