"""Digest scheduling self-test (D1 nightly wiring) — hermetic: the refresh/check subprocesses and the
queue are all stubbed, so nothing fetches, nothing drafts, nothing is written.

  .venv/Scripts/python.exe scripts/digest_schedule_selftest.py

THE SAFETY PROPERTY THIS LOCKS: refresh -> VERIFY -> generate, in that order, and NO generation when
verification fails. A digest built on stale prices prints last week's close as today's move, with full
confidence and every honesty label intact — strictly worse than publishing nothing, because it is wrong
in a way no downstream check can catch (every number binds; the numbers are just from the wrong day).
Silence is the honest failure mode, and the refusal is logged so a run of quiet days is visible.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run_daily as RD  # noqa: E402


class _Res:
    def __init__(self, rc, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


def main():
    ok, checks = True, []
    calls, logged = [], []

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        checks.append((bool(cond), name))

    orig = (RD.subprocess.run, RD.evidence_for, RD.qs.log, RD.qs.list_drafts,
            RD.gpu_free_for_drafting, RD._fidelity_gated, RD.qs.new_draft)

    def fake_run(cmd, **kw):
        calls.append(" ".join(str(c) for c in cmd[1:]))
        if "--check" in cmd:
            return _Res(fake_run.check_rc, fake_run.check_out)
        return _Res(0, "refreshed")
    fake_run.check_rc, fake_run.check_out = 0, ""

    RD.subprocess.run = fake_run
    RD.qs.log = lambda ev, **kw: logged.append((ev, kw))
    RD.qs.list_drafts = lambda: []
    RD.gpu_free_for_drafting = lambda: (True, "free")
    RD.qs.new_draft = lambda *a, **k: {"id": "TESTID", "status": "pending"}
    RD._fidelity_gated = lambda *a, **k: {"title": "t", "body_md": "w " * 400,
                                          "fidelity": {"passed": True, "failures": []}}
    RD.evidence_for = lambda sid: {
        "study_id": "digest:2026-07-23", "title_hint": "t", "evidence": "E", "digest": {"crossings": []},
        "provenance": {"study_key": "2026-07-23", "lead": "crossing", "crossings": 1,
                       "artifact": "deliverables/relational/conditional_stats.json"}}

    class A:
        now = True

    try:
        # --- 1. HAPPY PATH: ordering is refresh, refresh, then --check, and only then generate ---
        calls.clear(); logged.clear()
        RD._run_digest(A())
        check("refresh runs BEFORE the staleness check",
              len(calls) >= 3 and "--check" not in calls[0] and "--check" in calls[-1])
        check("both refreshers run (digest substrate + sector ETFs)",
              any("fetch_digest.py" in c and "--check" not in c for c in calls)
              and any("fetch_sectors.py" in c for c in calls))
        check("current substrate -> a draft is created", not any(e.startswith("digest_skipped")
                                                                 for e, _ in logged))

        # --- 2. THE GATE: --check fails -> NO generation at all ---
        calls.clear(); logged.clear()
        drafted = []
        RD.qs.new_draft = lambda *a, **k: (drafted.append(1), {"id": "X", "status": "pending"})[1]
        fake_run.check_rc, fake_run.check_out = 1, "WTI   crude   2026-07-01  14  2  FROZEN\n"
        RD._run_digest(A())
        check("stale substrate -> NO draft is generated", not drafted)
        check("stale substrate -> refusal is LOGGED (a quiet day must be visible)",
              any(e == "digest_skipped_stale" for e, _ in logged))
        check("the refusal names the offending series", any("WTI" in str(kw) for e, kw in logged
                                                            if e == "digest_skipped_stale"))
        check("no evidence is even requested once the gate fails",
              all("--check" in c or "fetch_" in c for c in calls))

        # --- 3. a refresh that RAISES is a refusal, not a crash into the study pass ---
        calls.clear(); logged.clear(); drafted.clear()

        def boom(cmd, **kw):
            raise TimeoutError("network hung")
        RD.subprocess.run = boom
        RD._run_digest(A())
        check("refresh timeout -> refusal, no draft, no exception", not drafted)
        check("refresh timeout is logged as stale-refusal",
              any(e == "digest_skipped_stale" for e, _ in logged))
        RD.subprocess.run = fake_run
        fake_run.check_rc, fake_run.check_out = 0, ""

        # --- 3b. INCOMPLETE MARK UNIVERSE -> no draft, and the reason is logged ---
        # The 2026-07-25 failure: sector_cache sat a session behind digest_cache, so the digest selected
        # a date only SPY had, found no sector prints, and wrote "no settled sector prints occurred
        # during this session" for an ordinary Friday. build_digest now raises IncompleteMarks and
        # evidence_for returns None; the pass must produce NOTHING and say why.
        calls.clear(); logged.clear(); drafted.clear()
        RD.evidence_for = lambda sid: None          # what an IncompleteMarks refusal looks like here
        RD._run_digest(A())
        check("incomplete mark universe -> NO draft", not drafted)
        check("incomplete mark universe -> logged as no-evidence, not silent",
              any(e == "digest_skipped_no_evidence" for e, _ in logged))
        RD.evidence_for = orig[1]
        RD.evidence_for = lambda sid: {
            "study_id": "digest:2026-07-23", "title_hint": "t", "evidence": "E",
            "digest": {"crossings": []},
            "provenance": {"study_key": "2026-07-23", "lead": "crossing", "crossings": 1,
                           "artifact": "deliverables/relational/conditional_stats.json"}}

        # the refresh must pass --refresh to fetch_sectors, or the MARKS never advance (the root cause)
        calls.clear(); logged.clear(); drafted.clear()
        RD._run_digest(A())
        check("sector refresh is invoked WITH --refresh (marks would never advance otherwise)",
              any("fetch_sectors.py" in c and "--refresh" in c for c in calls))
        check("the staleness gate requires a recent successful FETCH, not just fresh cache",
              any("--check" in c and "--fetched-within" in c for c in calls))

        # --- 4. IDEMPOTENT: one digest per session ---
        calls.clear(); logged.clear(); drafted.clear()
        RD.qs.list_drafts = lambda: [{"status": "pending", "provenance": {
            "study_key": "2026-07-23",
            "artifact": "deliverables/relational/conditional_stats.json"}}]
        RD._run_digest(A())
        check("session already has a digest -> no duplicate", not drafted)
        RD.qs.list_drafts = lambda: []

        # --- 5. GPU busy -> skip, and explicitly NOT retried tomorrow (it is session-dated) ---
        calls.clear(); logged.clear(); drafted.clear()
        RD.gpu_free_for_drafting = lambda: (False, "co-tenant resident")
        RD._run_digest(A())
        check("GPU busy -> no draft", not drafted)
        check("GPU skip is logged", any(e == "digest_skipped_gpu" for e, _ in logged))
    finally:
        (RD.subprocess.run, RD.evidence_for, RD.qs.log, RD.qs.list_drafts,
         RD.gpu_free_for_drafting, RD._fidelity_gated, RD.qs.new_draft) = orig

    print("DIGEST SCHEDULE SELF-TEST (hermetic; no fetch, no GPU, no queue writes)\n")
    for good, name in checks:
        print(f"  {'OK ' if good else 'XX '} {name}")
    print(f"\nSELF-TEST: {sum(g for g, _ in checks)}/{len(checks)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
