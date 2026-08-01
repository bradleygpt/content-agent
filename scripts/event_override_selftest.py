"""Both-directions selftest for the EVENT OVERRIDE trigger (2026-07-30).

The override's whole job is to be rare. A trigger that fires on quiet days is worse than no trigger,
because it displaces the cadence picker with noise; and a trigger that fires every day of a rout
produces a week of near-identical flagships (the 2026-07-23 midterm loop, again, in a new costume).

So both directions are tested, and the rout case is walked forward day by day rather than asserted
once — "a long rout fires once" is a claim about a SEQUENCE, and only a sequence can test it.

  .venv/Scripts/python.exe scripts/event_override_selftest.py
"""
from __future__ import annotations
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from content_agent.triggers import event_override            # noqa: E402
from content_agent.studies import CFG                        # noqa: E402

CHECKS, OK = [], [0]


def check(label: str, cond: bool):
    CHECKS.append((label, bool(cond)))
    OK[0] += bool(cond)
    print(f"  {'OK ' if cond else 'XX '} {label}")


def fake(**pcts):
    """A scan_fn returning fixed window returns, so no price data or network is touched."""
    def _f(window):
        return {a: {"pct": p, "from_date": "2026-06-30", "to_date": "2026-07-29",
                    "sessions": window} for a, p in pcts.items()}
    return _f


CFGO = CFG["triggers"]["event_override"]
THR, REARM, COOL = CFGO["threshold_pct"], CFGO["rearm_pct"], CFGO["cooldown_days"]
T0 = dt.datetime(2026, 7, 30, 21, 0, 0)


def main():
    print("EVENT-OVERRIDE SELF-TEST (hermetic; synthetic scans, no price data, no GPU)\n")

    # --- direction 1: MUST NOT FIRE on a quiet market -------------------------------------------
    st = {}
    check("quiet market does not fire (all anchors flat)",
          event_override(st, fake(ANCHOR_SPY=0.4, ANCHOR_XLE=-2.1), T0) is None)
    check("an ordinary correction does not fire (above threshold)",
          event_override({}, fake(ANCHOR_SPY=-11.0, ANCHOR_XLK=-14.9), T0) is None)
    check("a move just SHY of the threshold does not fire (boundary, outside)",
          event_override({}, fake(ANCHOR_SPY=THR + 0.1), T0) is None)
    check("a RALLY of the same magnitude does not fire (sign is not symmetric)",
          event_override({}, fake(ANCHOR_SPY=abs(THR) + 5.0), T0) is None)

    # --- direction 2: MUST FIRE on a real rout ---------------------------------------------------
    st = {}
    t = event_override(st, fake(ANCHOR_KOSPI=-33.19), T0)
    check("a rout fires", t is not None)
    check("fires as an override, ahead of the normal precedence list",
          bool(t) and t["trigger"] == "event_override" and t.get("override") is True)
    check("routes to the RECOVERY study for that anchor",
          bool(t) and t["study_id"] == "recovery:ANCHOR_KOSPI")
    check("the topic carries the measured fall, not an adjective",
          bool(t) and "33.2%" in t["topic"] and "20 sessions" in t["topic"])
    check("exactly at the threshold fires (boundary, inside)",
          event_override({}, fake(ANCHOR_SPY=THR), T0) is not None)

    # --- one flagship per pass; the WORST anchor wins ---------------------------------------------
    t = event_override({}, fake(ANCHOR_SPY=-21.0, ANCHOR_KOSPI=-33.2, ANCHOR_XLE=-25.0), T0)
    check("multiple qualifying anchors yield ONE trigger, the worst",
          bool(t) and t["study_id"] == "recovery:ANCHOR_KOSPI")

    # --- THE SEQUENCE TEST: a long rout fires exactly once -----------------------------------------
    st, fires = {}, []
    rout = [-33.2, -34.0, -31.5, -28.0, -25.0, -22.0, -21.0, -20.5, -24.0, -30.0]   # 10 days, all <= THR
    for i, pct in enumerate(rout):
        r = event_override(st, fake(ANCHOR_KOSPI=pct), T0 + dt.timedelta(days=i))
        if r:
            fires.append(i)
    check(f"a 10-day rout fires ONCE, on day 0 (fired days: {fires})", fires == [0])

    # --- re-arm: the rout has to actually END before it can fire again ------------------------------
    st = {}
    event_override(st, fake(ANCHOR_KOSPI=-33.2), T0)                       # fire
    partial = event_override(st, fake(ANCHOR_KOSPI=-12.0), T0 + dt.timedelta(days=40))
    check("a partial bounce (still below rearm) does not re-arm and does not fire", partial is None)
    check("  ... and the anchor is still recorded as disarmed",
          st["event_override"]["ANCHOR_KOSPI"]["armed"] is False)
    event_override(st, fake(ANCHOR_KOSPI=REARM + 1.0), T0 + dt.timedelta(days=41))   # rout ends
    check("recovering above rearm_pct re-arms the anchor",
          st["event_override"]["ANCHOR_KOSPI"]["armed"] is True)
    again = event_override(st, fake(ANCHOR_KOSPI=-33.2), T0 + dt.timedelta(days=42))
    check("a NEW rout after re-arm + cooldown fires again", again is not None)

    # --- cooldown backstop: re-armed but too soon ---------------------------------------------------
    st = {}
    event_override(st, fake(ANCHOR_KOSPI=-33.2), T0)
    event_override(st, fake(ANCHOR_KOSPI=REARM + 1.0), T0 + dt.timedelta(days=2))    # re-armed fast
    check("re-armed anchor still cannot fire inside the cooldown",
          event_override(st, fake(ANCHOR_KOSPI=-33.2), T0 + dt.timedelta(days=3)) is None)
    check("  ... and DOES fire once the cooldown has elapsed",
          event_override(st, fake(ANCHOR_KOSPI=-33.2),
                         T0 + dt.timedelta(days=COOL + 1)) is not None)

    # --- state + failure behaviour ------------------------------------------------------------------
    st = {}
    event_override(st, fake(ANCHOR_KOSPI=-33.2), T0)
    check("state is written back so the nightly can persist it", "event_override" in st)
    st2 = {}
    event_override(st2, fake(ANCHOR_SPY=-5.0), T0)
    check("state is written back even on a pass that did NOT fire (re-arms survive quiet days)",
          "event_override" in st2)

    def _boom(window):
        raise RuntimeError("price cache unavailable")
    check("a scan failure yields no override and does not raise",
          event_override({}, _boom, T0) is None)

    _saved = CFG["triggers"]["event_override"]
    try:
        CFG["triggers"]["event_override"] = {**_saved, "enabled": False}
        check("disabled in config: never fires, however bad the market",
              event_override({}, fake(ANCHOR_KOSPI=-90.0), T0) is None)
    finally:
        CFG["triggers"]["event_override"] = _saved
    check("  ... and re-enabling restores firing (the switch is not one-way)",
          event_override({}, fake(ANCHOR_KOSPI=-33.2), T0) is not None)

    # --- THE PASS, NOT THE COMPONENT (2026-07-31) ---------------------------------------------------
    # Everything above tests event_override() in isolation, and all 22 passed while the live nightly
    # was broken: it fired on KOSPI, disarmed it, then yielded at the GPU gate twenty lines later and
    # drafted nothing. A sequence claim needs the sequence AROUND the component, not just inside it.
    # These exercise the commit boundary directly, with no GPU, no model and no real state file.
    print()
    import run_daily as _rd
    import content_agent.queue_store as _qs

    _saved = []
    _orig_save, _orig_log = _qs.save_state, _qs.log
    _qs.save_state = lambda s: _saved.append(dict(s))
    _qs.log = lambda *a, **k: None
    _rd.qs.save_state, _rd.qs.log = _qs.save_state, _qs.log
    try:
        _trig = {"trigger": "event_override", "study_id": "recovery:ANCHOR_KOSPI"}
        _st = {"event_override": {"ANCHOR_KOSPI": {"armed": False, "last_fired": "2026-07-31T17:21:00"}}}

        # (a) the GPU-blocked pass: selection happened, NO draft was produced
        check("GPU-blocked pass commits NOTHING (draft is None)",
              _rd._commit_override_state(_trig, _st, None) is False and not _saved)
        check("  ... so the anchor is still ARMED for the next pass",
              not _saved)                       # nothing written -> the on-disk disarm never happened

        # (b) a draft exists -> the disarm is earned and persisted
        check("a queued draft commits the disarm",
              _rd._commit_override_state(_trig, _st, {"id": "x", "status": "pending"}) is True)
        check("  ... and what was written carries armed=False",
              bool(_saved) and _saved[-1]["event_override"]["ANCHOR_KOSPI"]["armed"] is False)

        # (c) a FAILED-FIDELITY draft still counts — it is queued and reviewable
        _saved.clear()
        check("a failed_fidelity draft still commits (the story reached a human)",
              _rd._commit_override_state(_trig, _st, {"id": "y", "status": "failed_fidelity"})
              and len(_saved) == 1)

        # (d) a non-override trigger never touches override state
        _saved.clear()
        check("a cadence trigger commits nothing",
              _rd._commit_override_state({"trigger": "cadence", "study_id": "pair:A|B"}, _st,
                                         {"id": "z", "status": "pending"}) is False and not _saved)

        # (e) SELECTION ITSELF MUST BE PURE — this is what let a hermetic test clobber production
        _saved.clear()
        _rd._select_trigger({"results_watermark": 0, "last_flagship_ts": 0,
                             "published_study_ids": []}, allow_override=False)
        check("_select_trigger writes NO state (a hermetic test cannot mutate production)",
              not _saved)
    finally:
        _qs.save_state, _qs.log = _orig_save, _orig_log
        _rd.qs.save_state, _rd.qs.log = _orig_save, _orig_log

    bad = [lbl for lbl, ok in CHECKS if not ok]
    print(f"\nSELF-TEST: {OK[0]}/{len(CHECKS)} " + ("PASS" if not bad else f"FAIL — {bad}"))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
