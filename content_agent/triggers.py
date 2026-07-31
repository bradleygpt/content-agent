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


def event_override(st: dict, scan_fn=None, now: dt.datetime | None = None) -> dict | None:
    """DID ANYTHING ACTUALLY HAPPEN? Checked BEFORE the cadence picker.

    The cadence picker asks "what is the strongest unpublished study", which is the right question on a
    quiet day and the wrong one during a rout. This asks the prior question, and when it fires it takes
    precedence over calendar, notable-results and cadence alike, and bypasses the redraft cooldown —
    that is what makes it an override rather than a fourth candidate in the queue.

    A LONG ROUT MUST FIRE ONCE, which needs two guards, not one. Measured over the full history at the
    shipped default (20 sessions, -20%): 683 firing anchor-days collapse to 189 distinct episodes, so a
    naive check would fire ~3.6 times per rout on average — and far more than that in the long ones,
    which are exactly the ones worth writing about.
      1. RE-ARM (structural): once fired for an anchor, that anchor cannot fire again until its window
         return climbs back above `rearm_pct`. The rout has to actually end. Hysteresis, not a timer —
         a drawdown oscillating either side of the threshold does not re-trigger.
      2. COOLDOWN (backstop): a hard per-anchor floor in days, so even a genuine second rout inside the
         same month cannot produce two flagships in a week.
    Both are config, both are editorial. State lives in st["event_override"] keyed by anchor.
    """
    cfg = CFG["triggers"].get("event_override", {})
    if not cfg.get("enabled", False):
        return None
    window = int(cfg.get("window_sessions", 20))
    threshold = float(cfg.get("threshold_pct", -20.0))
    rearm = float(cfg.get("rearm_pct", -10.0))
    cooldown_days = float(cfg.get("cooldown_days", 30))
    now = now or dt.datetime.now()

    if scan_fn is None:                                    # markets-llm owns the measurement
        import sys                                         # noqa: PLC0415
        _rel = str(MLL / "relational")                     # studies.py adds generation/, not relational/
        if _rel not in sys.path:
            sys.path.insert(0, _rel)
        import event_override as _eo                       # noqa: PLC0415
        scan_fn = _eo.window_returns
    try:
        rets = scan_fn(window)
    except Exception as e:                                 # noqa: BLE001
        print(f"[override] scan unavailable ({type(e).__name__}: {e}); no override this pass")
        return None

    mem = dict(st.get("event_override") or {})
    fired_now = None
    for anchor, d in sorted(rets.items(), key=lambda kv: kv[1]["pct"]):   # worst first
        prev = mem.get(anchor) or {}
        pct = float(d["pct"])
        if pct > rearm and prev.get("armed") is False:     # the rout ended — re-arm for next time
            mem[anchor] = {**prev, "armed": True}
            continue
        if pct > threshold:
            continue
        if prev.get("armed") is False:                     # still in the SAME rout
            continue
        last = prev.get("last_fired")
        if last:
            age = (now - dt.datetime.fromisoformat(last)).total_seconds() / 86400.0
            if age < cooldown_days:
                continue
        if fired_now is None:                              # one flagship per pass; worst anchor wins
            fired_now = (anchor, d)
    if fired_now is None:
        st["event_override"] = mem
        return None

    anchor, d = fired_now
    mem[anchor] = {"armed": False, "last_fired": now.isoformat(timespec="seconds"),
                   "pct": d["pct"], "to_date": d["to_date"]}
    st["event_override"] = mem
    return {"trigger": "event_override", "study_id": f"recovery:{anchor}", "override": True,
            "topic": f"a {abs(d['pct']):.1f}% fall over {d['sessions']} sessions "
                     f"({d['from_date']} to {d['to_date']}) — the drawdown itself is the story; "
                     f"how deep and how long, measured",
            "pct": d["pct"], "window_sessions": d["sessions"],
            "from_date": d["from_date"], "to_date": d["to_date"]}


def cadence_trigger(last_flagship_ts: float, published: set[str]) -> dict | None:
    days = (dt.datetime.now().timestamp() - (last_flagship_ts or 0)) / 86400
    if days < CFG["triggers"]["cadence_days"]:
        return None
    for sid in list_library():
        if sid not in published:
            return {"trigger": "cadence", "study_id": sid,
                    "topic": "weekly flagship — strongest unpublished study in the library"}
    return None
