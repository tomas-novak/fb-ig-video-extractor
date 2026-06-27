import json
import os
import gspread
from google.oauth2.service_account import Credentials
from models import VideoMetadata

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_client = None


def _get_client() -> gspread.Client:
    global _client
    if _client is None:
        # Local dev: cesta k JSON souboru; Railway: JSON obsah jako string v env
        if os.path.exists(os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")):
            creds = Credentials.from_service_account_file(
                os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"], scopes=_SCOPES
            )
        else:
            creds = Credentials.from_service_account_info(
                json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]), scopes=_SCOPES
            )
        _client = gspread.authorize(creds)
    return _client


def append_row(metadata: VideoMetadata) -> None:
    sheet_id = os.environ["GOOGLE_SHEETS_ID"]
    client = _get_client()
    sheet = client.open_by_key(sheet_id).sheet1
    sheet.append_row(metadata.to_sheets_row(), value_input_option="USER_ENTERED")


def read_rows() -> list[dict]:
    """Načte místa z tabulky pro mapu. Přeskočí hlavičku i nevalidní řádky."""
    sheet_id = os.environ["GOOGLE_SHEETS_ID"]
    client = _get_client()
    sheet = client.open_by_key(sheet_id).sheet1
    values = sheet.get_all_values()

    places = []
    for row in values:
        # zarovnání na 12 sloupců (A–L)
        if len(row) < 12:
            row = row + [""] * (12 - len(row))
        # validní řádek musí mít číselné lat/lng – tím odfiltrujeme i hlavičku
        try:
            lat = float(str(row[5]).replace(",", ".").strip())
            lng = float(str(row[6]).replace(",", ".").strip())
        except ValueError:
            continue
        if lat == 0 and lng == 0:
            continue
        places.append({
            "date": row[0],
            "url": row[1],
            "author": row[2],
            "title": row[3],
            "location_name": row[4],
            "lat": lat,
            "lng": lng,
            "category": (row[7] or "jiné").strip(),
            "tags": row[8],
            "summary": row[9],
            "source": row[11],
        })
    return places
