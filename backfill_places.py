"""One-off backfill: re-geocodes existing entries via Google Places.

Fills in columns P (place_id), Q (maps_url), R (geo_source) and fixes F/G (lat/lng).
Run locally: venv\\Scripts\\python backfill_places.py [--dry-run]
"""
import sys
from dotenv import load_dotenv
load_dotenv()

import gspread
from sheets import _get_sheet, NUM_COLS
from geocoder import geocode, maps_link
from dedup import _distance_km

DRY_RUN = "--dry-run" in sys.argv

sys.stdout.reconfigure(encoding="utf-8")
sheet = _get_sheet()
values = sheet.get_all_values()

updates = []   # gspread.Cell
report = []

for i, row in enumerate(values, start=1):
    if len(row) < NUM_COLS:
        row = row + [""] * (NUM_COLS - len(row))
    name = (row[4] or "").strip()
    if not name:
        continue  # header / invalid row
    try:
        old_lat = float(str(row[5]).replace(",", "."))
        old_lng = float(str(row[6]).replace(",", "."))
    except ValueError:
        continue
    pid = (row[15] or "").strip()
    if pid:
        # already has a place_id – only fix the old link format that the
        # Google Maps mobile app could not open
        if "/maps/place/?q=place_id:" in (row[16] or ""):
            updates.append(gspread.Cell(row=i, col=17,
                                        value=maps_link(pid, lat=old_lat, lng=old_lng)))
            report.append(f"row {i}: {name} -> maps_url format fixed")
        continue

    geo = geocode(name)
    if geo:
        dist = _distance_km(old_lat, old_lng, geo["lat"], geo["lng"])
        report.append(f"row {i}: {name} -> moved {dist:.1f} km ({geo['address'][:60]})")
        updates += [
            gspread.Cell(row=i, col=6, value=geo["lat"]),
            gspread.Cell(row=i, col=7, value=geo["lng"]),
            gspread.Cell(row=i, col=16, value=geo["place_id"]),
            gspread.Cell(row=i, col=17, value=geo["maps_url"]),
            gspread.Cell(row=i, col=18, value="places"),
        ]
    else:
        report.append(f"row {i}: {name} -> NOT FOUND (keeping Gemini estimate)")
        updates += [
            gspread.Cell(row=i, col=17, value=maps_link(name=name)),
            gspread.Cell(row=i, col=18, value="gemini"),
        ]

print("\n".join(report))
print(f"\nTotal cells to write: {len(updates)}")
if DRY_RUN:
    print("DRY RUN - nothing written.")
elif updates:
    sheet.update_cells(updates, value_input_option="USER_ENTERED")
    print("WRITTEN.")
