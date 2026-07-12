import json
import os
import uuid
import gspread
from google.oauth2.service_account import Credentials
from i18n import FALLBACK_CATEGORY
from models import VideoMetadata

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_client = None

# Sloupce: A datum, B url, C autor, D titulek, E místo, F lat, G lng,
#          H kategorie, I tagy, J shrnutí, K přepis, L zdroj, M group_id,
#          N video_id, O navštíveno, P place_id, Q maps_url, R geo_source
NUM_COLS = 18
URL_COL = 2
GROUP_COL = 13
VIDEO_ID_COL = 14
VISITED_COL = 15
PLACE_ID_COL = 16


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
    # table_range="A1": bez ukotvení si API hledá "tabulku" samo a úplně prázdný
    # sloupec (O: navštíveno) považuje za její konec – nové řádky pak zapisuje
    # posunuté doprava za sloupec R (viz posunuté řádky ze 7/2026).
    _get_sheet().append_row(metadata.to_sheets_row(), value_input_option="USER_ENTERED",
                            table_range="A1")


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
        "category": (row[7] or FALLBACK_CATEGORY).strip(),
        "tags": row[8],
        "summary": row[9],
        "source": row[11],
        "group_id": (row[12] or "").strip(),
        "video_id": (row[13] or "").strip(),
        "visited": (row[14] or "").strip().lower() in ("ano", "true", "1", "x"),
        "place_id": (row[15] or "").strip(),
        "maps_url": (row[16] or "").strip(),
        "geo_source": (row[17] or "").strip(),
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


def normalize_url(url: str) -> str:
    """Normalizace URL pro porovnání duplicit (bez query stringu, fragmentu a lomítka na konci)."""
    return url.strip().split("?")[0].split("#")[0].rstrip("/")


def find_duplicate(url: str = "", video_id: str = "") -> dict | None:
    """Najde existující záznam se stejnou URL (normalizovanou) nebo stejným video_id.
    Vrací {location_name, date, row} nebo None."""
    values = _get_sheet().get_all_values()
    norm = normalize_url(url) if url else ""
    for i, row in enumerate(values, start=1):
        if len(row) < NUM_COLS:
            row = row + [""] * (NUM_COLS - len(row))
        if norm and normalize_url(row[1]) == norm:
            return {"location_name": row[4], "date": row[0], "row": i}
        if video_id and (row[13] or "").strip() == video_id:
            return {"location_name": row[4], "date": row[0], "row": i}
    return None


def set_group_ids(row_to_group: dict[int, str]) -> None:
    """Nastaví group_id (sloupec M) daným řádkům. {číslo_řádku: group_id}"""
    sheet = _get_sheet()
    cells = [gspread.Cell(row=r, col=GROUP_COL, value=g) for r, g in row_to_group.items()]
    if cells:
        sheet.update_cells(cells, value_input_option="USER_ENTERED")


def find_by_place_id(place_id: str) -> dict | None:
    """Najde existující záznam se stejným place_id (= stejné místo podle Google).
    Vrací {row, group_id, location_name} nebo None."""
    if not place_id:
        return None
    values = _get_sheet().get_all_values()
    for i, row in enumerate(values, start=1):
        if len(row) < NUM_COLS:
            row = row + [""] * (NUM_COLS - len(row))
        if (row[15] or "").strip() == place_id:
            return {"row": i, "group_id": (row[12] or "").strip(), "location_name": row[4]}
    return None


def delete_place_rows(rows: list[int]) -> None:
    """Smaže dané řádky z tabulky. Maže od nejvyššího čísla, aby se zbylé neposunuly."""
    sheet = _get_sheet()
    for r in sorted(set(rows), reverse=True):
        sheet.delete_rows(r)


def set_visited(rows: list[int], visited: bool) -> None:
    """Označí řádky jako (ne)navštívené – sloupec O."""
    sheet = _get_sheet()
    value = "ano" if visited else ""
    cells = [gspread.Cell(row=r, col=VISITED_COL, value=value) for r in rows]
    if cells:
        sheet.update_cells(cells, value_input_option="USER_ENTERED")
