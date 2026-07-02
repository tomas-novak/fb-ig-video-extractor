import json
import os
import uuid
import gspread
from google.oauth2.service_account import Credentials
from models import VideoMetadata

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_client = None

# Sloupce: A datum, B url, C autor, D titulek, E místo, F lat, G lng,
#          H kategorie, I tagy, J shrnutí, K přepis, L zdroj, M group_id
NUM_COLS = 13


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


def _get_sheet():
    return _get_client().open_by_key(os.environ["GOOGLE_SHEETS_ID"]).sheet1


def new_group_id() -> str:
    return uuid.uuid4().hex[:8]


def append_row(metadata: VideoMetadata) -> None:
    if not metadata.group_id:
        metadata.group_id = new_group_id()
    _get_sheet().append_row(metadata.to_sheets_row(), value_input_option="USER_ENTERED")


def _parse_row(row: list, row_number: int) -> dict | None:
    """Převede řádek tabulky na dict. Vrací None pro hlavičku/nevalidní řádky."""
    if len(row) < NUM_COLS:
        row = row + [""] * (NUM_COLS - len(row))
    try:
        lat = float(str(row[5]).replace(",", ".").strip())
        lng = float(str(row[6]).replace(",", ".").strip())
    except ValueError:
        return None
    if lat == 0 and lng == 0:
        return None
    return {
        "row": row_number,
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
        "group_id": (row[12] or "").strip(),
    }


def read_rows() -> list[dict]:
    """Načte místa z tabulky (pro mapu i dedup). Přeskočí hlavičku i nevalidní řádky."""
    values = _get_sheet().get_all_values()
    places = []
    for i, row in enumerate(values, start=1):
        parsed = _parse_row(row, i)
        if parsed:
            places.append(parsed)
    return places


def set_group_ids(row_to_group: dict[int, str]) -> None:
    """Nastaví group_id (sloupec M) daným řádkům. {číslo_řádku: group_id}"""
    sheet = _get_sheet()
    cells = [gspread.Cell(row=r, col=NUM_COLS, value=g) for r, g in row_to_group.items()]
    if cells:
        sheet.update_cells(cells, value_input_option="USER_ENTERED")
