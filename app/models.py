from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
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


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    mode = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    trigger_source = Column(String(255), nullable=True)
    workbook_hash = Column(String(64), nullable=True, index=True)
    analytics_hash = Column(String(64), nullable=True, index=True)
    max_severity = Column(String(50), nullable=True)
    decision_summary = Column(Text, nullable=True)
    trigger_context = Column(Text, nullable=True)
    analytics_snapshot = Column(Text, nullable=True)
    state_snapshot = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)


class WorkbookSnapshot(Base):
    __tablename__ = "workbook_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    agent_run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=False, index=True)
    workbook_hash = Column(String(64), nullable=False, index=True)
    analytics_hash = Column(String(64), nullable=False, index=True)
    workbook_snapshot = Column(Text, nullable=True)
    analytics_snapshot = Column(Text, nullable=True)


class AgentFinding(Base):
    __tablename__ = "agent_findings"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    agent_run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=False, index=True)
    finding_key = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False)
    title = Column(Text, nullable=False)
    details = Column(Text, nullable=True)
    evidence_snapshot = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="open")


class AgentRecommendation(Base):
    __tablename__ = "agent_recommendations"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    agent_run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=False, index=True)
    finding_key = Column(String(255), nullable=False, index=True)
    priority = Column(String(50), nullable=False)
    responsible_unit = Column(String(255), nullable=True)
    recommendation = Column(Text, nullable=False)
    due_date = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="open")


class AgentAction(Base):
    __tablename__ = "agent_actions"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    agent_run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=False, index=True)
    action_type = Column(String(100), nullable=False)
    priority = Column(String(50), nullable=True)
    target = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
