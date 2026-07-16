"""Streak-rule + autonomy self-test — hermetic (temp queue/state; NEVER touches the live queue). Locks:
  - the 2026-07-15 streak rule: ordinary rejects are neutral; only correctness edits, post-pub
    corrections, and factually-wrong rejects of fidelity-passing drafts reset;
  - the 2026-07-16 autonomy rule: crossing the streak threshold makes autonomy ELIGIBLE, never ON —
    only the explicit enable_autonomy() confirm flips it, and the tripwire still reverts it.

  .venv/Scripts/python.exe scripts/streak_rule_selftest.py
"""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from content_agent import queue_store as qs  # noqa: E402


def _pass(md):  # a fidelity-passing stub report
    return {"passed": True, "failures": [], "labels": {}, "numeric": [], "directional": []}


def _fail():
    return {"passed": False, "failures": [{"type": "NO-MATCH", "token": "x", "detail": ""}],
            "labels": {}, "numeric": [], "directional": []}


def main():
    tmp = Path(tempfile.mkdtemp(prefix="streak_selftest_"))
    qs.QUEUE = tmp / "queue"
    qs.STATE = tmp / "state"
    qs.STATE_FILE = qs.STATE / "state.json"
    qs.AUDIT = qs.STATE / "audit_log.jsonl"

    class _Adapter:
        name = "manual"
        def publish_post(self, *a, **k): return {"mode": "manual", "url_or_path": str(tmp / "x.md")}
        def publish_note(self, *a, **k): return {"mode": "manual", "url_or_path": str(tmp / "x.md")}

    ok, checks = True, []

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        checks.append((bool(cond), name))

    def streak():
        return qs.load_state()["streak"]

    def mk(passed=True):
        rep = _pass("x") if passed else _fail()
        return qs.new_draft("note", "t", "body", {"study_key": "s"}, rep, "ev")

    # two clean approvals -> streak 2
    qs.approve(mk()["id"], "none", _Adapter())
    qs.approve(mk()["id"], "none", _Adapter())
    check("two approvals -> streak 2", streak() == 2)

    # ordinary reject of a fidelity-passing draft -> NEUTRAL
    qs.reject(mk(passed=True)["id"], "not wanted")
    check("ordinary reject is neutral (stays 2)", streak() == 2)

    # ordinary reject of a failed-fidelity draft -> NEUTRAL
    qs.reject(mk(passed=False)["id"], "stale")
    check("reject of failed-fidelity draft is neutral (stays 2)", streak() == 2)

    # factually_wrong reject of a FIDELITY-PASSING draft -> RESET
    qs.reject(mk(passed=True)["id"], "bad read", factually_wrong=True)
    check("factually-wrong reject of fidelity-passing draft RESETS (0)", streak() == 0)

    # rebuild to 3, then factually_wrong reject of a FAILED-fidelity draft -> still NEUTRAL
    for _ in range(3):
        qs.approve(mk()["id"], "none", _Adapter())
    check("rebuilt to 3", streak() == 3)
    qs.reject(mk(passed=False)["id"], "wrong but checker already caught it", factually_wrong=True)
    check("factually-wrong reject of FAILED-fidelity draft stays neutral (3)", streak() == 3)

    # correctness approval still resets
    d = mk()
    qs.approve(d["id"], "correctness", _Adapter())
    check("correctness approval RESETS (0)", streak() == 0)

    # --- autonomy: unlock-then-confirm (threshold patched to 2 for the test) ------------------------
    qs.CFG = {**qs.CFG, "autonomy": {**qs.CFG["autonomy"], "required_streak": 2}}

    def enabled():
        return qs.load_state()["autonomy_enabled"]

    try:
        qs.enable_autonomy()
        check("enable below threshold raises", False)
    except ValueError:
        check("enable below threshold raises", True)
    qs.approve(mk()["id"], "none", _Adapter())
    check("below threshold: not eligible", not qs.autonomy_eligible())
    qs.approve(mk()["id"], "none", _Adapter())
    check("crossing threshold does NOT enable autonomy", streak() == 2 and not enabled())
    check("crossing threshold makes it ELIGIBLE", qs.autonomy_eligible())
    audit = (qs.AUDIT.read_text(encoding="utf-8"))
    check("eligibility crossing is logged", '"event": "autonomy_eligible"' in audit)
    st = qs.enable_autonomy()
    check("explicit confirm enables", st["autonomy_enabled"] and enabled())
    check("enabled -> no longer 'eligible'", not qs.autonomy_eligible())
    try:
        qs.enable_autonomy()
        check("double-enable raises", False)
    except ValueError:
        check("double-enable raises", True)
    # tripwire still reverts explicit enablement
    d = mk()
    qs.approve(d["id"], "none", _Adapter())
    qs.factual_correction(d["id"], "post-pub factual error")
    check("tripwire reverts autonomy + streak", not enabled() and streak() == 0)
    check("after tripwire: not eligible again until threshold re-crossed", not qs.autonomy_eligible())

    print("STREAK-RULE + AUTONOMY SELF-TEST (hermetic temp state; live queue untouched)\n")
    for good, name in checks:
        print(f"  {'OK ' if good else 'XX '} {name}")
    passed = sum(g for g, _ in checks)
    print(f"\nSELF-TEST: {passed}/{len(checks)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
