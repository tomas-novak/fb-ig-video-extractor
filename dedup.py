"""Duplicate place check: distance prefilter + a verdict from Claude.

Runs on demand (the dedup command in Telegram). It changes nothing
automatically – it returns suggestions and the user decides about merging
using the buttons in Telegram.
"""
import json
import os
import anthropic

from geocoder import distance_km as _distance_km
from i18n import t

MAX_DISTANCE_KM = 8.0  # Gemini coordinates are estimates; the same place can land ~5.5 km apart (Chvojenec)
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("Missing ANTHROPIC_API_KEY environment variable")
        _client = anthropic.Anthropic()
    return _client


def find_candidate_pairs(places: list[dict]) -> list[tuple[dict, dict, float]]:
    """Find pairs of places closer than MAX_DISTANCE_KM that are not already in the same group."""
    pairs = []
    for i in range(len(places)):
        for j in range(i + 1, len(places)):
            a, b = places[i], places[j]
            # skip already merged ones (same non-empty group_id)
            if a["group_id"] and a["group_id"] == b["group_id"]:
                continue
            d = _distance_km(a["lat"], a["lng"], b["lat"], b["lng"])
            if d <= MAX_DISTANCE_KM:
                pairs.append((a, b, d))
    return pairs


def judge_pair(a: dict, b: dict, distance_km: float) -> dict:
    """Ask Claude whether this is the same place. Returns {same: bool, reason: str}."""
    client = _get_client()
    prompt = f"""Compare two place entries from a travel map and decide whether they are the SAME place (just named/pinned differently), or two DIFFERENT places.

Entry A:
- Name: {a['location_name']}
- Coordinates: {a['lat']}, {a['lng']}
- Category: {a['category']}
- Summary: {a['summary'][:300]}

Entry B:
- Name: {b['location_name']}
- Coordinates: {b['lat']}, {b['lng']}
- Category: {b['category']}
- Summary: {b['summary'][:300]}

Distance between the coordinates: {distance_km:.2f} km (note that the coordinates are AI estimates and may be imprecise).

Return ONLY JSON: {{"same": true/false, "reason": "short justification {t('dedup_reason_lang')} (max 1 sentence)"}}"""

    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_verdict(msg.content[0].text)


def parse_verdict(raw: str) -> dict:
    """Parse Claude's JSON verdict. An unparseable response = not a duplicate (fail safe)."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw)
        return {"same": bool(data.get("same")), "reason": str(data.get("reason", ""))}
    except (json.JSONDecodeError, AttributeError):
        return {"same": False, "reason": t("dedup_reason_unparseable", raw=raw[:100])}


def find_duplicates(places: list[dict]) -> list[dict]:
    """Full check: prefilter + place_id match / Claude verdicts.
    Returns a list of suggestions: {a, b, distance_km, reason} only for pairs marked as the same."""
    suggestions = []
    for a, b, d in find_candidate_pairs(places):
        pid_a, pid_b = a.get("place_id", ""), b.get("place_id", "")
        if pid_a and pid_b:
            if pid_a == pid_b:
                # Same Google place – a certain match, no need for Claude
                suggestions.append({"a": a, "b": b, "distance_km": d,
                                    "reason": t("dedup_reason_place_id")})
            # different place_id = different places -> skip (without asking Claude)
            continue
        verdict = judge_pair(a, b, d)
        if verdict["same"]:
            suggestions.append({"a": a, "b": b, "distance_km": d, "reason": verdict["reason"]})
    return suggestions
