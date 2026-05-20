from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class TriggerEvent(Base):
    __tablename__ = "trigger_events"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sheet_title = Column(String(255), nullable=True)
    changed_column = Column(String(255), nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    event_timestamp = Column(String(100), nullable=True)
    payload_snapshot = Column(Text, nullable=True)


class ReportLog(Base):
    __tablename__ = "report_logs"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    report_path = Column(String(1024), nullable=False)
    email_status = Column(String(255), nullable=True)
    analytics_snapshot = Column(Text, nullable=True)
    workbook_snapshot = Column(Text, nullable=True)
    narrative_snippet = Column(Text, nullable=True)


class EscalationEvent(Base):
    __tablename__ = "escalation_events"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    escalation_type = Column(String(255), nullable=False)
    reason = Column(Text, nullable=True)
    recipients = Column(Text, nullable=False)
    details = Column(Text, nullable=True)
