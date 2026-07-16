"""Reconstruct the approval streak from the audit log under the CURRENT (2026-07-15) streak rule, which
differs from the rule in force when most of the log was written. Reporting/audit tool — does NOT write
state unless --apply is passed.

CURRENT RULE (see queue_store docstring):
  - approve (none/taste)                      -> +1
  - approve (correctness)                     -> reset 0   (a fact had to be fixed)
  - factual_correction_tripwire               -> reset 0   (post-publication correction)
  - reject of a draft NEVER approved          -> NEUTRAL   (housekeeping — stale/dup/not-wanted)
  - reject of a PREVIOUSLY-APPROVED draft     -> reset 0   (a published piece retracted = a
                                                            post-publication correction / a
                                                            fidelity-passing draft judged wrong)

The last bullet is the reconstruction's one judgment call: the historical log predates the
reject(factually_wrong=...) flag, so we infer intent from the data — a reject whose id appears as an
earlier `approved` event is a retraction of published content (resets); every other reject is ordinary
housekeeping (neutral).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "state" / "audit_log.jsonl"


def reconstruct(verbose: bool = True):
    events = [json.loads(l) for l in AUDIT.read_text(encoding="utf-8").splitlines() if l.strip()]
    approved_ids = {e["id"] for e in events if e["event"] == "approved"}
    streak, rows = 0, []
    for e in events:
        ev, did = e["event"], e.get("id", "")
        delta = None
        if ev == "approved":
            if e.get("edit_class") == "correctness":
                streak, delta = 0, "RESET (correctness edit)"
            else:
                streak += 1
                delta = f"+1 -> {streak}"
        elif ev == "factual_correction_tripwire":
            streak, delta = 0, "RESET (post-pub correction)"
        elif ev == "rejected":
            if did in approved_ids:                    # retraction of a previously-approved (published) draft
                streak, delta = 0, "RESET (retraction of published draft)"
            else:
                delta = f"neutral (stays {streak})"
        if delta:
            rows.append((e["ts"], ev, did, delta))
    if verbose:
        for ts, ev, did, delta in rows:
            print(f"  {ts}  {ev:9} {did:24} {delta}")
    return streak


def main():
    apply = "--apply" in sys.argv
    print("STREAK RECONSTRUCTION (current rule; audit-log replay)\n")
    streak = reconstruct(verbose=True)
    print(f"\nRECONSTRUCTED STREAK: {streak}")
    from content_agent.queue_store import load_state, save_state  # noqa
    st = load_state()
    print(f"state.json streak:    {st['streak']}   (autonomy_enabled={st['autonomy_enabled']})")
    if apply:
        st["streak"] = streak
        save_state(st)
        print(f"--apply: wrote streak={streak} to state.json (autonomy flag untouched)")
    elif streak != st["streak"]:
        print("(run with --apply to persist the reconstructed value)")
    else:
        print("(matches stored state — no change needed)")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
