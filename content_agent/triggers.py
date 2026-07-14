"""The three triggers (checked by the daily pass).

1. CALENDAR — upcoming events inside their approach window. Midterm/presidential election days are
   rule-derived (first Tuesday after the first Monday of November; midterms in years % 4 == 2,
   presidentials in years % 4 == 0), so no guessed dates. The FOMC's FUTURE schedule is not derivable from
   the corpus (which holds past meetings only) and is deliberately NOT hardcoded — FOMC content arrives via
   the notable-results and cadence paths instead. The 2026-11-03 midterm is the launch arc.
2. NOTABLE RESULTS — recent markets-llm run outputs whose answers carried engine evidence
   (event/recovery/pair escalation with evidence found) become draft candidates.
3. CADENCE — one flagship per week regardless; falls back to the strongest unpublished library study.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path

from .studies import MLL, CFG, list_library


def _election_day(year: int) -> dt.date:
    d = dt.date(year, 11, 1)
    first_monday = d + dt.timedelta(days=(0 - d.weekday()) % 7)
    return first_monday + dt.timedelta(days=1)


def calendar_triggers(today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today()
    windows = CFG["triggers"]["calendar_windows_weeks"]
    out = []
    for year in (today.year, today.year + 1):
        kind = ("midterm_election" if year % 4 == 2 else "pres_election" if year % 4 == 0 else None)
        if not kind or kind not in windows:
            continue
        eday = _election_day(year)
        weeks_out = (eday - today).days / 7.0
        if 0 < weeks_out <= windows[kind]:
            out.append({"trigger": "calendar", "study_id": f"event:{kind}",
                        "topic": f"{kind.replace('_', ' ')} on {eday.isoformat()} is "
                                 f"{weeks_out:.1f} weeks away — countdown piece",
                        "weeks_out": round(weeks_out, 1)})
    return out


def notable_results(watermark_ts: float) -> list[dict]:
    """Scan markets-llm run outputs newer than the watermark for engine-fired answers. The persisted
    gen.json strips escalation state — the record of a fired escalation lives in each run's streaming
    events.jsonl ({"type":"escalation","fired":true,...}, with the query in the "submitted" event)."""
    runs = MLL / "deliverables" / "runs"
    out = []
    if not runs.exists():
        return out
    for ej in runs.rglob("events.jsonl"):
        try:
            if ej.stat().st_mtime <= watermark_ts:
                continue
            lines = ej.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        query = ""
        for line in lines:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") == "submitted":
                query = ev.get("query") or query
            if ev.get("type") == "escalation" and ev.get("fired"):
                kind = ev.get("kind")
                if kind == "event" and ev.get("event"):
                    sid = f"event:{ev['event']}"
                elif kind == "recovery" and ev.get("anchor"):
                    sid = f"recovery:{ev['anchor']}"
                elif kind == "comparative" and ev.get("pairs"):
                    sid = "pair:" + "|".join(ev["pairs"][0])
                elif ev.get("pair"):
                    sid = "pair:" + "|".join(ev["pair"])
                else:
                    continue
                out.append({"trigger": "notable_result", "study_id": sid,
                            "topic": f"a real query the engine answered with measured evidence: "
                                     f"\"{query[:140]}\"",
                            "run": str(ej.parent.parent.name)})
                break                                     # one candidate per run
    return out


def cadence_trigger(last_flagship_ts: float, published: set[str]) -> dict | None:
    days = (dt.datetime.now().timestamp() - (last_flagship_ts or 0)) / 86400
    if days < CFG["triggers"]["cadence_days"]:
        return None
    for sid in list_library():
        if sid not in published:
            return {"trigger": "cadence", "study_id": sid,
                    "topic": "weekly flagship — strongest unpublished study in the library"}
    return None
