"""Jednorázový backfill: přegeokóduje existující záznamy přes Google Places.

Doplnní sloupce P (place_id), Q (maps_url), R (geo_source) a opraví F/G (lat/lng).
Spouštět lokálně: venv\\Scripts\\python backfill_places.py [--dry-run]
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
        continue  # hlavička / nevalidní řádek
    try:
        old_lat = float(str(row[5]).replace(",", "."))
        old_lng = float(str(row[6]).replace(",", "."))
    except ValueError:
        continue
    pid = (row[15] or "").strip()
    if pid:
        # place_id už má – jen případná oprava starého formátu odkazu,
        # který mobilní aplikace Google Maps neuměla otevřít
        if "/maps/place/?q=place_id:" in (row[16] or ""):
            updates.append(gspread.Cell(row=i, col=17,
                                        value=maps_link(pid, lat=old_lat, lng=old_lng)))
            report.append(f"radek {i}: {name} -> opraven format maps_url")
        continue

    geo = geocode(name)
    if geo:
        dist = _distance_km(old_lat, old_lng, geo["lat"], geo["lng"])
        report.append(f"radek {i}: {name} -> posun {dist:.1f} km ({geo['address'][:60]})")
        updates += [
            gspread.Cell(row=i, col=6, value=geo["lat"]),
            gspread.Cell(row=i, col=7, value=geo["lng"]),
            gspread.Cell(row=i, col=16, value=geo["place_id"]),
            gspread.Cell(row=i, col=17, value=geo["maps_url"]),
            gspread.Cell(row=i, col=18, value="places"),
        ]
    else:
        report.append(f"radek {i}: {name} -> NENALEZENO (ponechan odhad Gemini)")
        updates += [
            gspread.Cell(row=i, col=17, value=maps_link(name=name)),
            gspread.Cell(row=i, col=18, value="gemini"),
        ]

print("\n".join(report))
print(f"\nCelkem bunek k zapisu: {len(updates)}")
if DRY_RUN:
    print("DRY RUN - nic nezapsano.")
elif updates:
    sheet.update_cells(updates, value_input_option="USER_ENTERED")
    print("ZAPSANO.")
