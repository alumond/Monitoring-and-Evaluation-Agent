from functools import lru_cache
from pydantic import EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_service_account_file: str = Field(..., validation_alias="GOOGLE_SERVICE_ACCOUNT_FILE")
    spreadsheet_id: str = Field(..., validation_alias="GOOGLE_SHEETS_SPREADSHEET_ID")
    gemini_api_url: str = Field(..., validation_alias="GEMINI_API_URL")
    gemini_api_key: str = Field(..., validation_alias="GEMINI_API_KEY")

    smtp_host: str = Field(..., validation_alias="SMTP_HOST")
    smtp_port: int = Field(587, validation_alias="SMTP_PORT")
    smtp_username: str = Field(..., validation_alias="SMTP_USERNAME")
    smtp_password: str = Field(..., validation_alias="SMTP_PASSWORD")
    email_from: EmailStr = Field(..., validation_alias="EMAIL_FROM")
    default_recipients: str = Field("", validation_alias="EMAIL_TO")

    escalation_enabled: bool = Field(False, validation_alias="ESCALATION_ENABLED")
    escalation_recipients: str = Field("", validation_alias="ESCALATION_EMAIL_TO")
    escalation_kpi_threshold: float = Field(90.0, validation_alias="ESCALATION_KPI_THRESHOLD")
    escalation_subject_format: str = Field(
        "Action Required: KPI Target Breach - {project_name} - {period}",
        validation_alias="ESCALATION_SUBJECT_FORMAT",
    )
    escalation_message_template: str = Field(
        "A KPI target breach has been detected for {project_name} during the {period} review cycle. This note summarizes the facts, likely delivery implications, and corrective actions requiring management follow-up.",
        validation_alias="ESCALATION_MESSAGE_TEMPLATE",
    )

    google_calendar_enabled: bool = Field(False, validation_alias="GOOGLE_CALENDAR_ENABLED")
    google_calendar_id: str = Field("", validation_alias="GOOGLE_CALENDAR_ID")
    google_calendar_attendees: str = Field("", validation_alias="GOOGLE_CALENDAR_ATTENDEES")
    google_calendar_timezone: str = Field("Africa/Lagos", validation_alias="GOOGLE_CALENDAR_TIMEZONE")
    google_calendar_reminder_days: int = Field(3, validation_alias="GOOGLE_CALENDAR_REMINDER_DAYS")
    google_calendar_reminder_hour: int = Field(9, validation_alias="GOOGLE_CALENDAR_REMINDER_HOUR")
    google_calendar_send_updates: str = Field("all", validation_alias="GOOGLE_CALENDAR_SEND_UPDATES")

    autonomous_scheduler_enabled: bool = Field(False, validation_alias="AUTONOMOUS_SCHEDULER_ENABLED")
    autonomous_scheduler_interval_seconds: int = Field(3600, validation_alias="AUTONOMOUS_SCHEDULER_INTERVAL_SECONDS")
    autonomous_scheduler_run_on_startup: bool = Field(False, validation_alias="AUTONOMOUS_SCHEDULER_RUN_ON_STARTUP")
    autonomous_always_send_report: bool = Field(False, validation_alias="AUTONOMOUS_ALWAYS_SEND_REPORT")
    autonomous_report_on_findings: bool = Field(True, validation_alias="AUTONOMOUS_REPORT_ON_FINDINGS")
    autonomous_operational_alerts_enabled: bool = Field(True, validation_alias="AUTONOMOUS_OPERATIONAL_ALERTS_ENABLED")
    autonomous_operational_alert_recipients: str = Field("", validation_alias="AUTONOMOUS_OPERATIONAL_ALERT_EMAIL_TO")

    agent_writeback_enabled: bool = Field(False, validation_alias="AGENT_WRITEBACK_ENABLED")
    agent_actions_sheet_title: str = Field("Agent Actions", validation_alias="AGENT_ACTIONS_SHEET_TITLE")

    decision_kpi_critical_threshold: float = Field(70.0, validation_alias="DECISION_KPI_CRITICAL_THRESHOLD")
    decision_budget_low_utilization_threshold: float = Field(70.0, validation_alias="DECISION_BUDGET_LOW_UTILIZATION_THRESHOLD")
    decision_budget_overrun_threshold: float = Field(110.0, validation_alias="DECISION_BUDGET_OVERRUN_THRESHOLD")
    decision_overdue_high_count: int = Field(5, validation_alias="DECISION_OVERDUE_HIGH_COUNT")

    log_db_url: str = Field("sqlite:///./db/report_audit.db", validation_alias="LOG_DB_URL")
    project_name: str = Field("M&E Intelligence Program", validation_alias="PROJECT_NAME")
    brand_logo_path: str = Field("./assets/Almond AI consulting.png", validation_alias="BRAND_LOGO_PATH")
    report_filename_template: str = Field("me_report_{timestamp}.pdf", validation_alias="REPORT_FILENAME_TEMPLATE")
    report_subject_format: str = Field("M&E Report - {project_name} - {period}", validation_alias="REPORT_SUBJECT_FORMAT")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
