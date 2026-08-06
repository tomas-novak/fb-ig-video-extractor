"""Pomocný skript: vygeneruje railway-variables.local.txt pro rychlé vložení
do Railway (dashboard -> Variables -> Raw Editor). Tento soubor se
NEcommituje (je v .gitignore).

Projde všechny proměnné z lokálního .env automaticky, takže nezastarává,
když se v .env.example objeví nová proměnná. Výjimky:
- GOOGLE_SERVICE_ACCOUNT_FILE (cesta k souboru, jen pro lokální vývoj) se
  převede na GOOGLE_SERVICE_ACCOUNT_JSON (obsah souboru na jeden řádek).
  Pokud soubor na dané cestě neexistuje (např. nezměněný placeholder
  z .env.example), nebo je GOOGLE_SERVICE_ACCOUNT_JSON v .env už přímo
  vyplněné (typicky když je .env zkopírované ze serveru), použije se to.
- HOST, PORT, PUBLIC_URL a FFMPEG_LOCATION se přeskakují - jsou to buď
  hodnoty specifické pro tenhle konkrétní počítač (FFMPEG_LOCATION by na
  Railway ukazovala na neexistující cestu a rozbila by ffmpeg, i když ho
  nixpacks.toml nainstaluje), nebo je Railway řeší samo (PORT, a doménu
  poskytuje přes RAILWAY_PUBLIC_DOMAIN, které main.py používá automaticky,
  pokud PUBLIC_URL není nastavené).
- Víceřádkové hodnoty (typicky INSTAGRAM_COOKIES) se zapíší v uvozovkách,
  ať se při vložení do Railway nerozpadnou na samostatné řádky.
"""
import json
import os
from dotenv import dotenv_values

env = dotenv_values(".env")
skip = {"HOST", "PORT", "PUBLIC_URL", "FFMPEG_LOCATION", "GOOGLE_SERVICE_ACCOUNT_FILE"}
lines = []

sa_file = env.get("GOOGLE_SERVICE_ACCOUNT_FILE")
sa_json = env.get("GOOGLE_SERVICE_ACCOUNT_JSON")
if sa_file and os.path.exists(sa_file):
    sa = json.load(open(sa_file, encoding="utf-8"))
    lines.append(f"GOOGLE_SERVICE_ACCOUNT_JSON={json.dumps(sa, ensure_ascii=False)}")
elif sa_json:
    lines.append(f"GOOGLE_SERVICE_ACCOUNT_JSON={sa_json}")
elif sa_file:
    print(f"POZOR: GOOGLE_SERVICE_ACCOUNT_FILE={sa_file!r} neexistuje - service account chybí ve výstupu.")
else:
    print("POZOR: GOOGLE_SERVICE_ACCOUNT_FILE ani GOOGLE_SERVICE_ACCOUNT_JSON není v .env vyplněné.")

for key, value in env.items():
    if key in skip or key == "GOOGLE_SERVICE_ACCOUNT_JSON" or not value:
        continue
    if "\n" in value:
        value = f'"{value}"'
    lines.append(f"{key}={value}")

with open("railway-variables.local.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Hotovo: railway-variables.local.txt ({len(lines)} promennych)")
