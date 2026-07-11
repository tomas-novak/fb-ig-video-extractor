"""Kontrola duplicitních míst: předfiltr podle vzdálenosti + verdikt od Claude.

Volá se na povel (/zkontroluj v Telegramu). Nic nemění automaticky –
vrací návrhy, o sloučení rozhoduje uživatel tlačítky v Telegramu.
"""
import json
import os
import anthropic

from geocoder import distance_km as _distance_km

MAX_DISTANCE_KM = 8.0  # souřadnice od Gemini jsou odhady, u stejného místa i ~5,5 km od sebe (Chvojenec)
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("Chybí proměnná prostředí ANTHROPIC_API_KEY")
        _client = anthropic.Anthropic()
    return _client


def find_candidate_pairs(places: list[dict]) -> list[tuple[dict, dict, float]]:
    """Najde páry míst blíž než MAX_DISTANCE_KM, které ještě nejsou ve stejné skupině."""
    pairs = []
    for i in range(len(places)):
        for j in range(i + 1, len(places)):
            a, b = places[i], places[j]
            # už sloučené (stejné neprázdné group_id) přeskočit
            if a["group_id"] and a["group_id"] == b["group_id"]:
                continue
            d = _distance_km(a["lat"], a["lng"], b["lat"], b["lng"])
            if d <= MAX_DISTANCE_KM:
                pairs.append((a, b, d))
    return pairs


def judge_pair(a: dict, b: dict, distance_km: float) -> dict:
    """Zeptá se Claude, zda jde o stejné místo. Vrací {same: bool, reason: str}."""
    client = _get_client()
    prompt = f"""Porovnej dva záznamy míst z cestovní mapy a rozhodni, zda jde o STEJNÉ místo (jen jinak pojmenované/zaměřené), nebo o dvě RŮZNÁ místa.

Záznam A:
- Název: {a['location_name']}
- Souřadnice: {a['lat']}, {a['lng']}
- Kategorie: {a['category']}
- Shrnutí: {a['summary'][:300]}

Záznam B:
- Název: {b['location_name']}
- Souřadnice: {b['lat']}, {b['lng']}
- Kategorie: {b['category']}
- Shrnutí: {b['summary'][:300]}

Vzdálenost mezi souřadnicemi: {distance_km:.2f} km (pozor, souřadnice jsou odhady AI, mohou být nepřesné).

Vrať POUZE JSON: {{"same": true/false, "reason": "krátké zdůvodnění česky (max 1 věta)"}}"""

    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_verdict(msg.content[0].text)


def parse_verdict(raw: str) -> dict:
    """Parsuje JSON verdikt od Claude. Neparsovatelná odpověď = ne-duplikát (fail safe)."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw)
        return {"same": bool(data.get("same")), "reason": str(data.get("reason", ""))}
    except (json.JSONDecodeError, AttributeError):
        return {"same": False, "reason": f"neparsovatelná odpověď: {raw[:100]}"}


def find_duplicates(places: list[dict]) -> list[dict]:
    """Kompletní kontrola: předfiltr + place_id shoda / Claude verdikty.
    Vrací seznam návrhů: {a, b, distance_km, reason} jen pro páry označené jako stejné."""
    suggestions = []
    for a, b, d in find_candidate_pairs(places):
        pid_a, pid_b = a.get("place_id", ""), b.get("place_id", "")
        if pid_a and pid_b:
            if pid_a == pid_b:
                # Stejné Google místo – jistá shoda, Claude není potřeba
                suggestions.append({"a": a, "b": b, "distance_km": d,
                                    "reason": "Stejné místo podle Google Maps (place_id)."})
            # různá place_id = různá místa -> přeskočit (bez dotazu na Claude)
            continue
        verdict = judge_pair(a, b, d)
        if verdict["same"]:
            suggestions.append({"a": a, "b": b, "distance_km": d, "reason": verdict["reason"]})
    return suggestions
