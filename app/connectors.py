from typing import Any, Dict, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .config import get_settings


class GoogleSheetsConnector:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        credentials = service_account.Credentials.from_service_account_file(
            self.settings.google_service_account_file,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
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
