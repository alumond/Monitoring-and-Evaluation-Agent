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
        "Escalation Alert - {project_name} - {period}",
        validation_alias="ESCALATION_SUBJECT_FORMAT",
    )
    escalation_message_template: str = Field(
        "Escalation detected for {project_name}. Review the attached operational action summary.",
        validation_alias="ESCALATION_MESSAGE_TEMPLATE",
    )

    log_db_url: str = Field("sqlite:///./db/report_audit.db", validation_alias="LOG_DB_URL")
    project_name: str = Field("M&E Intelligence Program", validation_alias="PROJECT_NAME")
    brand_logo_path: str = Field("./assets/logo.png", validation_alias="BRAND_LOGO_PATH")
    report_filename_template: str = Field("me_report_{timestamp}.pdf", validation_alias="REPORT_FILENAME_TEMPLATE")
    report_subject_format: str = Field("M&E Report - {project_name} - {period}", validation_alias="REPORT_SUBJECT_FORMAT")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
