import json
from typing import Dict, Any, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from .config import get_settings
from .models import Base, TriggerEvent, ReportLog, EscalationEvent


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
