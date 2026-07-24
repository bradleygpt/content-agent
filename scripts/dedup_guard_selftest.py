"""Daily-pass dedup guard self-test — hermetic (fixture draft lists; the live queue is never read or
written). Locks the 2026-07-23 fix for the redundant-regeneration loop.

  .venv/Scripts/python.exe scripts/dedup_guard_selftest.py

THE BUG: calendar_triggers fires EVERY day an event sits inside its countdown window and has no memory
of what it already produced — unlike cadence_trigger, which skips studies already in
published_study_ids. That asymmetry produced 25 near-identical midterm drafts over 8 days on a study
that was already published. Two guards now break the loop:
  - redraft_cooldown_days: don't redraft a study drafted within N days (counts rejected drafts too, so
    clearing the queue as redundant does NOT license an immediate redraft);
  - max_pending_per_study: don't stack unreviewed drafts for one study.
"""
from __future__ import annotations
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from run_daily import duplicate_pending, days_since_last_draft  # noqa: E402

MID, FOMC = "event:midterm_election", "event:fomc_meeting"
NOW = dt.datetime(2026, 7, 23, 13, 0, 0)


def draft(status, kind, sid, days_ago, now=NOW):
    return {"status": status, "kind": kind, "provenance": {"study_id": sid},
            "created": (now - dt.timedelta(days=days_ago)).isoformat(timespec="seconds")}


def main():
    ok, checks = True, []

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        checks.append((bool(cond), name))

    # --- max_pending_per_study ---------------------------------------------------------------------
    three_pending = [draft("pending", "note", MID, 0) for _ in range(3)]
    check("counts pending publishable drafts for the study", duplicate_pending(MID, three_pending) == 3)
    noise = three_pending + [
        draft("published", "note", MID, 1), draft("rejected", "note", MID, 1),
        draft("failed_fidelity", "note", MID, 1), draft("pending", "note", FOMC, 0),
        {"status": "review_item", "kind": "research", "provenance": {}, "created": NOW.isoformat()},
    ]
    check("published/rejected/failed/research/other-study all excluded",
          duplicate_pending(MID, noise) == 3)
    check("other study counted independently", duplicate_pending(FOMC, noise) == 1)
    check("empty queue -> 0", duplicate_pending(MID, []) == 0)

    # --- redraft_cooldown_days ---------------------------------------------------------------------
    check("never drafted -> None (no cooldown block)", days_since_last_draft(MID, [], NOW) is None)
    fresh = [draft("pending", "note", MID, 0.2)]
    check("drafted 0.2d ago -> under a 7d cooldown",
          round(days_since_last_draft(MID, fresh, NOW), 1) == 0.2)
    old = [draft("published", "flagship", MID, 30)]
    check("drafted 30d ago -> over a 7d cooldown", days_since_last_draft(MID, old, NOW) > 7)
    # THE LOOP-BREAKER: drafts cleared as redundant still count, so clearing does not license a redraft
    just_rejected = [draft("rejected", "note", MID, 0.05) for _ in range(25)]
    since = days_since_last_draft(MID, just_rejected, NOW)
    check("REJECTED drafts still count -> clearing the pile does NOT license an immediate redraft",
          since is not None and since < 7)
    # newest wins when history is mixed
    mixed = [draft("rejected", "note", MID, 20), draft("published", "note", MID, 2)]
    check("uses the MOST RECENT draft", round(days_since_last_draft(MID, mixed, NOW)) == 2)
    check("cooldown is per-study (other study unaffected)",
          days_since_last_draft(FOMC, mixed, NOW) is None)

    # --- fall-through: a blocked trigger must not idle the pass ------------------------------------
    import run_daily
    orig_dp, orig_ds = run_daily.duplicate_pending, run_daily.days_since_last_draft
    try:
        # midterm on cooldown, everything else free
        run_daily.days_since_last_draft = lambda sid, *a, **k: 0.2 if "midterm" in sid else None
        run_daily.duplicate_pending = lambda sid, *a, **k: 0
        run_daily.calendar_triggers = lambda *a, **k: [
            {"trigger": "calendar", "study_id": MID, "topic": "countdown"}]
        run_daily.notable_results = lambda *a, **k: []
        run_daily.cadence_trigger = lambda *a, **k: {"trigger": "cadence",
                                                     "study_id": "event:pres_election", "topic": "x"}
        run_daily.list_library = lambda: [MID, "event:pres_election", "recovery:ANCHOR_SPY"]
        run_daily.qs.log = lambda *a, **k: None
        state = {"results_watermark": 0, "last_flagship_ts": 0, "published_study_ids": []}
        got = run_daily._select_trigger(state)
        check("blocked trigger FALLS THROUGH to the next candidate",
              got is not None and got["study_id"] == "event:pres_election")

        # every trigger blocked -> library backfill supplies an unpublished study
        run_daily.days_since_last_draft = lambda sid, *a, **k: (0.2 if sid in
                                                                (MID, "event:pres_election") else None)
        got2 = run_daily._select_trigger(state)
        check("all triggers blocked -> backfill picks an unpublished library study",
              got2 is not None and got2["study_id"] == "recovery:ANCHOR_SPY"
              and got2["trigger"] == "backfill")

        # backfill NEVER redrafts an already-published study
        state_pub = {**state, "published_study_ids": ["recovery:ANCHOR_SPY"]}
        run_daily.cadence_trigger = lambda *a, **k: None
        got3 = run_daily._select_trigger(state_pub)
        check("backfill excludes already-published studies", got3 is None)

        # nothing blocked -> highest-precedence trigger still wins (no behavior change)
        run_daily.days_since_last_draft = lambda sid, *a, **k: None
        got4 = run_daily._select_trigger(state)
        check("nothing blocked -> precedence unchanged (calendar first)",
              got4 is not None and got4["study_id"] == MID and got4["trigger"] == "calendar")
    finally:
        run_daily.duplicate_pending, run_daily.days_since_last_draft = orig_dp, orig_ds

    print("DEDUP-GUARD SELF-TEST (hermetic fixtures; live queue untouched)\n")
    for good, name in checks:
        print(f"  {'OK ' if good else 'XX '} {name}")
    passed = sum(g for g, _ in checks)
    print(f"\nSELF-TEST: {passed}/{len(checks)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
