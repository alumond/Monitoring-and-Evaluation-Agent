from datetime import datetime
from typing import Any, Dict, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .config import get_settings


class GoogleSheetsConnector:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        if self.settings.agent_writeback_enabled:
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = service_account.Credentials.from_service_account_file(
            self.settings.google_service_account_file,
            scopes=scopes,
        )
        self.service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self.spreadsheet_id = self.settings.spreadsheet_id

    def fetch_workbook(self) -> List[Dict[str, Any]]:
        spreadsheet = self.service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id,
            includeGridData=False,
        ).execute()
        sheets = spreadsheet.get("sheets", [])
        workbook = []
        for sheet in sheets:
            title = sheet["properties"]["title"]
            values = self._fetch_sheet_values(title)
            if not values:
                continue
            workbook.append({
                "title": title,
                "headers": [str(cell).strip() for cell in values[0]],
                "rows": [[str(cell).strip() for cell in row] for row in values[1:]],
            })
        return workbook

    def _fetch_sheet_values(self, title: str) -> List[List[Any]]:
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=title,
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="FORMATTED_STRING",
            ).execute()
            return result.get("values", [])
        except HttpError as exc:
            raise RuntimeError(f"Unable to read sheet {title}: {exc}")

    def _quote_sheet_title(self, title: str) -> str:
        return "'" + title.replace("'", "''") + "'"

    def _sheet_exists(self, title: str) -> bool:
        spreadsheet = self.service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id,
            includeGridData=False,
        ).execute()
        return any(sheet["properties"]["title"] == title for sheet in spreadsheet.get("sheets", []))

    def _ensure_sheet_with_headers(self, title: str, headers: List[str]) -> None:
        if not self._sheet_exists(title):
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
            ).execute()

        quoted_title = self._quote_sheet_title(title)
        current = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{quoted_title}!1:1",
        ).execute().get("values", [])
        if not current:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{quoted_title}!A1",
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()

    def append_agent_actions(self, recommendations: List[Dict[str, Any]], run_id: int = 0) -> Dict[str, Any]:
        if not recommendations:
            return {"status": "skipped", "reason": "No recommendations to write back."}

        headers = [
            "Created At",
            "Agent Run ID",
            "Finding Key",
            "Priority",
            "Responsible Unit",
            "Recommendation",
            "Due Date",
            "Status",
        ]
        title = self.settings.agent_actions_sheet_title
        self._ensure_sheet_with_headers(title, headers)
        timestamp = datetime.utcnow().isoformat() + "Z"
        rows = [
            [
                timestamp,
                run_id or "",
                item.get("finding_key", ""),
                item.get("priority", ""),
                item.get("responsible_unit", ""),
                item.get("recommendation", ""),
                item.get("due_date", ""),
                item.get("status", "open"),
            ]
            for item in recommendations
        ]
        quoted_title = self._quote_sheet_title(title)
        result = self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{quoted_title}!A:H",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()
        return {
            "status": "written",
            "sheet": title,
            "rows": len(rows),
            "updated_range": result.get("updates", {}).get("updatedRange", ""),
        }
