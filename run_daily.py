"""The daily pass — triggers -> draft -> FIDELITY -> queue. Lowest-priority GPU tenant.

  .venv/Scripts/python.exe run_daily.py [--now] [--study STUDY_ID] [--skip-notes]

--now      single GPU check instead of the polite polling window (for manual runs)
--study    force a specific study (bypasses triggers; used for launch content)
Order of precedence when multiple triggers fire: calendar > notable results > cadence. One flagship per
pass at most; notes are queued from the same study's evidence. If the GPU never frees, exits quietly —
drafting is batchable and time-flexible; tomorrow's pass tries again.

AUTONOMY: if (and only if) the autonomy flag is ON, fidelity-PASSING drafts are auto-approved through the
adapter. Ships OFF; see queue_store for the flip criteria + tripwire.
"""
from __future__ import annotations
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from content_agent import queue_store as qs                      # noqa: E402
from content_agent.studies import CFG, evidence_for              # noqa: E402
from content_agent.triggers import calendar_triggers, notable_results, cadence_trigger  # noqa: E402
from content_agent.news import topical_hints                     # noqa: E402
from content_agent.gpu import wait_for_gpu, gpu_free_for_drafting  # noqa: E402
from content_agent.drafter import draft_flagship, draft_note     # noqa: E402
from content_agent.fidelity import run_fidelity                  # noqa: E402
from content_agent.publisher import get_adapter                  # noqa: E402


def _fidelity_gated(make, evidence_text: str, **kw) -> dict:
    """Draft -> check -> on hard fail regenerate ONCE with the violations injected -> second fail is
    queued as FAILED-FIDELITY (never silently dropped, never publishable in that state)."""
    d = make(**kw)
    rep = run_fidelity(d["body_md"], evidence_text)
    if not rep["passed"]:
        fails = [f"{f['type']}: {f['token']} — {f['detail']}" for f in rep["failures"]][:12]
        d = make(**kw, fidelity_failures=fails)
        rep = run_fidelity(d["body_md"], evidence_text)
    d["fidelity"] = rep
    return d


def _note_focuses(study_id: str) -> list[str]:
    if study_id.startswith("sector_event:midterm"):
        return ["the SPREAD between the deepest sector (semiconductors, median -27.0%) and the shallowest "
                "(consumer staples, median -8.9%) inside the five midterm windows",
                "how financials (median -21.0%) fell versus the S&P 500 baseline (median -15.7%) across the "
                "five midterms",
                "the defensive sectors — utilities (median -10.3%) and consumer staples (median -8.9%) — "
                "versus the market in midterm drawdowns"]
    if study_id.startswith("event:midterm"):
        return ["the median depth across the five measured midterm drawdowns",
                "how long recovery took (median and range) across the five midterms",
                "the 2022 midterm case (deepest of the five)"]
    if study_id.startswith("event:fomc"):
        return ["the median drawdown around the 166 measured FOMC meetings",
                "the recovery median and its long tail across the 166 meetings"]
    return ["the median drawdown depth and count of episodes",
            "the median time-to-recover and its range",
            "the deepest named stress episode"]


def _ensure_queue_server():
    """Self-heal: if the loopback queue server is down, spawn it detached (no console window)."""
    import requests
    import subprocess
    try:
        requests.get(f"http://{CFG['server']['host']}:{CFG['server']['port']}/api/content/health",
                     timeout=3)
        return
    except Exception:
        pass
    pyw = Path(sys.executable).parent / "pythonw.exe"
    subprocess.Popen([str(pyw if pyw.exists() else sys.executable), "-m", "content_agent.server"],
                     cwd=str(Path(__file__).resolve().parent),
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print("[daily] queue server was down — respawned")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", action="store_true")
    ap.add_argument("--study", default=None)
    ap.add_argument("--topic", default=None, help="editorial framing override for the flagship")
    ap.add_argument("--skip-notes", action="store_true")
    ap.add_argument("--notes-only", action="store_true")
    ap.add_argument("--research-only", action="store_true",
                    help="run ONLY the hypothesis-intake nightly (register #6 C-1)")
    args = ap.parse_args()

    # RESEARCH-ONLY shortcut (register #6 C-1): the hypothesis nightly without any drafting.
    if args.research_only:
        _ensure_queue_server()
        gcfg = CFG["gpu"]
        free = gpu_free_for_drafting()[0] if args.now else wait_for_gpu(gcfg["attempts"],
                                                                        gcfg["sleep_seconds"])
        if not free:
            print("[daily] GPU never freed — research nightly yields; tomorrow retries")
            return
        from content_agent.hypotheses import run_nightly
        print("[daily] research nightly (arXiv q-fin intake)...")
        s = run_nightly()
        print(f"[daily] research: {s['papers']} papers, {s['tickets']} tickets "
              f"({s['no_claim']} no-claim), {s['testable']} testable / {s['untestable']} untestable / "
              f"{s['unverified']} unverified; verdicts: {s['verdicts']}")
        return

    _ensure_queue_server()
    st = qs.load_state()
    if args.study:
        trig = {"trigger": "manual", "study_id": args.study,
                "topic": args.topic or "manual/launch draft"}
    else:
        trigs = calendar_triggers()
        trigs += notable_results(st["results_watermark"])
        cad = cadence_trigger(st["last_flagship_ts"], set(st["published_study_ids"]))
        if cad:
            trigs.append(cad)
        if not trigs:
            print("[daily] no trigger fired; nothing to draft")
            return
        trig = trigs[0]
    print(f"[daily] trigger: {trig['trigger']} -> {trig['study_id']} ({trig.get('topic','')[:80]})")

    ev = evidence_for(trig["study_id"])
    if not ev:
        print(f"[daily] no evidence for {trig['study_id']} — abort")
        return

    # TRIGGER CONTEXT rides into the CHECKABLE evidence: framing numbers a countdown piece legitimately
    # states ("16.0 weeks away", the election date) come from trigger/provenance metadata, not the study
    # block — without this they false-fail NO-MATCH (observed 2026-07-14). The drafter still receives the
    # pure study block as its only source of claims; the trigger numbers reach it via the topic line, and
    # the checker accepts them because they are provenance, not invention. Stored as the draft's evidence
    # so the /drafts edit-recheck path binds them identically.
    trig_bits = [b for b in (str(trig.get("topic") or ""),
                             f"{trig['weeks_out']} weeks until the event"
                             if trig.get("weeks_out") is not None else "") if b]
    ev_check = ev["evidence"] + ("\n\nTRIGGER CONTEXT (provenance metadata; legitimate numeric "
                                 "evidence):\n- " + "\n- ".join(trig_bits) if trig_bits else "")

    gcfg = CFG["gpu"]
    free = gpu_free_for_drafting()[0] if args.now else wait_for_gpu(gcfg["attempts"], gcfg["sleep_seconds"])
    if not free:
        print(f"[daily] GPU never freed ({gpu_free_for_drafting()[1]}) — yielding; tomorrow's pass retries")
        return

    hints = [h for h in topical_hints() if h["study_id"] == trig["study_id"]]
    prov = {**ev["provenance"], "study_id": ev["study_id"], "drafted": dt.datetime.now().isoformat()}

    if not args.notes_only:
        print("[daily] drafting flagship...")
        fl = _fidelity_gated(draft_flagship, ev_check,
                             topic=f"{trig.get('topic','')} — study: {ev['title_hint']}",
                             evidence=ev["evidence"], news_hints=hints)
        d = qs.new_draft("flagship", fl["title"], fl["body_md"], prov, fl["fidelity"], ev_check, trig)
        print(f"[daily]   flagship {d['id']} -> {d['status']}")

    if not args.skip_notes:
        for focus in _note_focuses(trig["study_id"])[:CFG["drafting"]["notes_per_flagship"]]:
            nt = _fidelity_gated(draft_note, ev_check, evidence=ev["evidence"], stat_focus=focus)
            nd = qs.new_draft("note", nt["title"], nt["body_md"], prov, nt["fidelity"], ev_check, trig)
            print(f"[daily]   note {nd['id']} -> {nd['status']}")

    # RESEARCH NIGHTLY (register #6 C-1) — runs AFTER draft work, lowest priority: only if enabled and
    # the GPU is STILL free (a co-tenant that arrived during drafting wins; tomorrow retries).
    if CFG.get("research", {}).get("enabled") and gpu_free_for_drafting()[0]:
        from content_agent.hypotheses import run_nightly
        print("[daily] research nightly (arXiv q-fin intake)...")
        try:
            s = run_nightly()
            print(f"[daily] research: {s['papers']} papers, {s['tickets']} tickets, "
                  f"{s['testable']} testable / {s['untestable']} untestable / {s['unverified']} unverified")
        except Exception as e:                       # research must never break the content pass
            print(f"[daily] research nightly failed (non-fatal): {e}")

    # autonomy (ships OFF): only fidelity-PASSING drafts, only when the flag is on
    if qs.load_state()["autonomy_enabled"]:
        for dd in qs.list_drafts():
            if dd["status"] == "pending" and dd["fidelity"].get("passed"):
                qs.approve(dd["id"], "none", get_adapter(CFG))
                print(f"[daily] AUTONOMY: auto-approved {dd['id']}")

    st = qs.load_state()
    st["results_watermark"] = dt.datetime.now().timestamp()
    qs.save_state(st)
    print("[daily] done")


if __name__ == "__main__":
    main()
