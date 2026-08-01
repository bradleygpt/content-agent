"""The daily pass — triggers -> draft -> FIDELITY -> queue. Lowest-priority GPU tenant.

EVENT OVERRIDE runs before all of it: "did anything actually happen today" is a prior question to
"what is the strongest unpublished study", and on the day a market falls 30% the cadence picker is
asking the wrong one. See content_agent.triggers.event_override for the re-arm/cooldown discipline
that keeps a long rout to a single flagship.

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
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from content_agent import queue_store as qs                      # noqa: E402
from content_agent.studies import CFG, evidence_for, list_library              # noqa: E402
from content_agent.triggers import (calendar_triggers, notable_results, cadence_trigger,  # noqa: E402
                                    event_override)
from content_agent.news import topical_hints                     # noqa: E402
from content_agent.gpu import wait_for_gpu, gpu_free_for_drafting  # noqa: E402
from content_agent.drafter import draft_flagship, draft_note     # noqa: E402
from content_agent.fidelity import run_fidelity                  # noqa: E402
from content_agent.publisher import get_adapter                  # noqa: E402


def _fidelity_gated(make, evidence_text: str, **kw) -> dict:
    """Draft -> check -> on hard fail regenerate ONCE with the violations injected -> second fail is
    queued as FAILED-FIDELITY (never silently dropped, never publishable in that state)."""
    d = make(**kw)
    rep = run_fidelity(d["body_md"], evidence_text, d.get("kind"))
    if not rep["passed"]:
        fails = [f"{f['type']}: {f['token']} — {f['detail']}" for f in rep["failures"]][:12]
        d = make(**kw, fidelity_failures=fails)
        rep = run_fidelity(d["body_md"], evidence_text, d.get("kind"))
    d["fidelity"] = rep
    return d


def duplicate_pending(study_id: str, drafts: list | None = None) -> int:
    """PENDING publishable drafts already queued for this study — the trigger's memory lives in the
    queue. Pure/injectable so the dedup guard is testable without touching the live queue."""
    drafts = qs.list_drafts() if drafts is None else drafts
    return sum(1 for d in drafts
               if d.get("status") == "pending" and d.get("kind") in ("flagship", "note")
               and (d.get("provenance") or {}).get("study_id") == study_id)


def days_since_last_draft(study_id: str, drafts: list | None = None, now: dt.datetime | None = None):
    """Days since this study was LAST drafted, whatever became of that draft (approved, rejected, still
    pending). None if never. Rejected drafts count: a study cleared as redundant must not be redrafted
    the very next pass — that is the loop this guard exists to break."""
    drafts = qs.list_drafts() if drafts is None else drafts
    now = now or dt.datetime.now()
    stamps = [d["created"] for d in drafts
              if d.get("kind") in ("flagship", "note")
              and (d.get("provenance") or {}).get("study_id") == study_id and d.get("created")]
    if not stamps:
        return None
    return (now - dt.datetime.fromisoformat(max(stamps))).total_seconds() / 86400.0


def blocked_reason(study_id: str):
    """The dedup guards as a PREDICATE -> (reason, audit_event, extra) or (None, None, {}).

    Two guards, both born from the 2026-07-23 loop: calendar_triggers fires every day an event sits in
    its countdown window with no memory of what it produced (25 near-identical midterm drafts in 8 days
    on an already-published study), while cadence_trigger correctly skips published studies but never
    got a turn because calendar takes precedence."""
    cooldown = CFG["triggers"].get("redraft_cooldown_days", 7)
    since = days_since_last_draft(study_id)
    if since is not None and since < cooldown:
        return (f"drafted {since:.1f}d ago (redraft_cooldown_days={cooldown}) — a countdown piece is "
                "meant to recur weekly, not daily", "daily_skipped_cooldown",
                {"days_since": round(since, 2), "cooldown_days": cooldown})
    max_pending = CFG["triggers"].get("max_pending_per_study", 3)
    n = duplicate_pending(study_id)
    if n >= max_pending:
        return (f"{n} pending draft(s) already awaiting review (max_pending_per_study={max_pending})",
                "daily_skipped_duplicate", {"pending": n, "max_pending": max_pending})
    return None, None, {}


def _commit_override_state(trig: dict, st: dict, draft: dict | None) -> bool:
    """Persist the override's DISARM — and only once a draft actually exists.

    The guard's promise is "a long rout fires once". It cannot keep that promise by disarming at
    SELECTION time, because everything between selection and a queued draft can still fail: the GPU
    gate, an empty evidence block, a drafting exception. On 2026-07-31 the first real pass proved it,
    firing on KOSPI and then yielding at the GPU with nothing written.

    A FAILED-FIDELITY draft still counts as fired. It exists, it is in the queue, it is reviewable,
    and re-drafting the same rout tomorrow would produce the same piece — the override's job was to
    put the story in front of a human, and it did.
    """
    if not trig or trig.get("trigger") != "event_override" or draft is None:
        return False
    qs.save_state(st)
    qs.log("event_override_committed", study_id=trig["study_id"], draft_id=draft.get("id"),
           draft_status=draft.get("status"))
    print(f"[daily]   override state committed — {trig['study_id']} disarmed until it re-arms")
    return True


def _select_trigger(st: dict, allow_override: bool = True):
    """Pick the first candidate the guards allow — FALL THROUGH, never stop at the first block.

    Blocking a trigger must not idle the whole pipeline: when the midterm countdown is on cooldown there
    are (as of 2026-07-23) 17 never-drafted studies waiting. Order: real triggers by precedence
    (calendar > notable > cadence), then a LIBRARY BACKFILL over unpublished studies. Backfill never
    includes already-published studies — redrafting published material is the redundancy just removed."""
    # THE OVERRIDE RUNS FIRST and returns immediately — it is not a fourth candidate in the precedence
    # list. It bypasses blocked_reason deliberately: the redraft cooldown exists so a COUNTDOWN piece
    # recurs weekly rather than daily, and it has no business silencing a market that just fell 30%.
    # The override carries its own re-arm + cooldown (triggers.event_override), which is the guard that
    # actually fits the case. Its state mutation is persisted here, whether or not it fired, so a
    # re-arm is not lost on a pass that produced nothing.
    # `allow_override` exists for the HERMETIC tests, not as a feature. The override is the one step in
    # trigger selection that reads live prices, so a test of the fall-through logic would otherwise
    # depend on what the market did today — passing in July and failing in October for no code reason.
    # The nightly never passes it.
    #
    # THIS FUNCTION DOES NOT PERSIST. It mutates `st` in memory and leaves the commit to the caller,
    # which writes only once a draft actually exists (_commit_override_state). Two live bugs, one
    # cause — a save_state() here made selection impure:
    #   1. The 2026-07-31 pass fired the override at 17:21, DISARMED KOSPI, then yielded at the GPU
    #      gate twenty lines later and drafted nothing. The rout spent its one shot on a pass that
    #      produced no piece, and re-arm needs the drawdown to actually END, so a deep rout would
    #      never fire again.
    #   2. dedup_guard_selftest calls this with a synthetic three-key state. The unconditional save
    #      wrote that fixture over the REAL state.json — which is what cleared event_override and
    #      reset results_watermark to 0. A hermetic test was mutating production because the function
    #      it tested had grown a side effect.
    # Losing an in-memory RE-ARM on a pass that drafts nothing is harmless and deliberate: the next
    # pass recomputes it from the same prices and re-arms again. Only the DISARM must survive, and it
    # must survive only when it was earned.
    ovr = event_override(st) if allow_override else None
    if ovr:
        print(f"[daily] EVENT OVERRIDE: {ovr['study_id']} {ovr['pct']:+.2f}% over "
              f"{ovr['window_sessions']} sessions ({ovr['from_date']}..{ovr['to_date']}) "
              f"— taking precedence over calendar/notable/cadence")
        qs.log("daily_event_override", study_id=ovr["study_id"], trigger="event_override",
               pct=ovr["pct"], window_sessions=ovr["window_sessions"], to_date=ovr["to_date"])
        return ovr

    trigs = calendar_triggers()
    trigs += notable_results(st["results_watermark"])
    cad = cadence_trigger(st["last_flagship_ts"], set(st["published_study_ids"]))
    if cad:
        trigs.append(cad)
    published = set(st["published_study_ids"])
    seen = {t["study_id"] for t in trigs}
    for sid in list_library():
        if sid not in seen and sid not in published:
            trigs.append({"trigger": "backfill", "study_id": sid,
                          "topic": "library backfill — measured study not yet published"})
            seen.add(sid)
    if not trigs:
        print("[daily] no trigger fired and no unpublished study in the library; nothing to draft")
        return None
    for c in trigs:
        why, event, extra = blocked_reason(c["study_id"])
        if why:
            print(f"[daily]   skip {c['study_id']} ({c['trigger']}): {why}")
            qs.log(event, study_id=c["study_id"], trigger=c["trigger"], **extra)
            continue
        return c
    print(f"[daily] all {len(trigs)} candidate studies are on cooldown or already queued; "
          "nothing to draft this pass")
    return None


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


# ======================================================================================================
# THE DAILY MEASURED DIGEST — refresh, VERIFY, generate. Never generate on unverified prices.
# ======================================================================================================
def _refresh_substrate() -> tuple[bool, str]:
    """Refresh the Yahoo digest substrate and the sector-ETF cache, then VERIFY every series is current.
    -> (ok, detail). ok=False means the digest must not run this session.

    Both refreshers honour the session gate, so a mid-session run stores nothing rather than storing a
    provisional bar. The verify step is a SEPARATE call to --check after the refresh: a fetch that
    silently failed leaves the old cache in place and looks like success from the exit code alone."""
    mll = Path(CFG["markets_llm_root"])
    py = CFG.get("digest", {}).get("python", sys.executable)
    # --refresh on fetch_sectors is LOAD-BEARING: without it the script skips every already-cached
    # ticker (correct for its original one-time role, fatal as a daily refresher) and the 12 sector
    # MARKS never advance. That is what produced a digest reporting "no settled sector prints" for an
    # ordinary session.
    for script, args, label in [("relational/fetch_digest.py", [], "digest substrate"),
                                ("relational/fetch_sectors.py", ["--refresh"], "sector ETFs")]:
        try:
            r = subprocess.run([py, script, *args], cwd=str(mll), capture_output=True, text=True,
                               timeout=900)
            tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
            print(f"[digest] refresh {label}: exit {r.returncode} — {tail[0][:110]}")
        except Exception as e:
            return False, f"{label} refresh raised {type(e).__name__}: {e}"
    # THE GATE: non-zero means at least one series is stale, missing, or WAS NOT SUCCESSFULLY FETCHED
    # in this run. The fetch-recency requirement is the part cache age cannot supply: a market holiday
    # legitimately leaves every US series 2 business days back (measured max gap = 2 over 2 years), so
    # no cache-age tolerance can separate "the market was shut" from "the refresh silently failed". A
    # successful fetch can: on a holiday it succeeds and returns a pre-holiday bar; on a failure it does
    # not happen at all. 60 minutes is generous for a refresh that takes seconds.
    try:
        r = subprocess.run([py, "relational/fetch_digest.py", "--check", "--fetched-within", "60"],
                           cwd=str(mll), capture_output=True, text=True, timeout=300)
    except Exception as e:
        return False, f"staleness check raised {type(e).__name__}: {e}"
    if r.returncode != 0:
        bad = [ln.strip() for ln in (r.stdout or "").splitlines() if "FROZEN" in ln or "MISSING" in ln]
        return False, "; ".join(bad)[:400] or "staleness check failed"
    return True, "all series current"


def _run_digest(args) -> None:
    """One session's digest, or an explicit refusal. Never raises into the study pass."""
    ok, detail = _refresh_substrate()
    if not ok:
        print(f"[digest] REFUSING to generate — substrate not current: {detail}")
        print("[digest] a digest built on stale prices prints old closes as today's move; "
              "no digest is the honest outcome.")
        qs.log("digest_skipped_stale", reason=detail)
        return

    ev = evidence_for("digest:")
    if not ev:
        print("[digest] no settled session / missing conditional artifact — skipping")
        qs.log("digest_skipped_no_evidence")
        return
    as_of = ev["provenance"]["study_key"]
    # IDEMPOTENT: one digest per session. A second run the same day must not stack a duplicate — the
    # same discipline the dedup guards enforce for studies, applied to the session key.
    if any((d.get("provenance") or {}).get("study_key") == as_of
           and (d.get("provenance") or {}).get("artifact", "").endswith("conditional_stats.json")
           and d.get("status") in ("pending", "published", "approved")
           for d in qs.list_drafts()):
        print(f"[digest] session {as_of} already has a digest in the queue — skipping (idempotent)")
        return

    gcfg = CFG["gpu"]
    free = gpu_free_for_drafting()[0] if args.now else wait_for_gpu(gcfg["attempts"],
                                                                    gcfg["sleep_seconds"])
    if not free:
        print(f"[digest] GPU never freed ({gpu_free_for_drafting()[1]}) — skipping; the digest is "
              f"session-dated and is NOT retried tomorrow")
        qs.log("digest_skipped_gpu", as_of=as_of)
        return

    print(f"[digest] session {as_of} ({detail}); lead={ev['provenance']['lead']}, "
          f"crossings={ev['provenance']['crossings']}")
    prov = {**ev["provenance"], "study_id": ev["study_id"],
            "drafted": dt.datetime.now().isoformat()}
    trig = {"trigger": "digest", "study_id": ev["study_id"], "topic": ev["title_hint"]}
    # THE DAILY IDENTITY (option (b), adopted 2026-07-27): flagship when the market moved (a
    # crossing), NOTE when it didn't. Measured basis: the flagship shape went 0-for-8 on quiet
    # evidence and two shortened-flagship arms failed their A/B on the same frozen session, while
    # the note form passed unattended on first exposure to a new evidence class. Idempotence,
    # session gating and refuse-on-stale are identical on both paths — they all run above this line.
    if ev["provenance"]["lead"] == "dispersion":
        fl = _fidelity_gated(draft_note, ev["evidence"], evidence=ev["evidence"],
                             stat_focus="the session's sector spread, its notable leg, and the "
                                        "similar-sessions composition")
        kind = "note"
    else:
        fl = _fidelity_gated(draft_flagship, ev["evidence"], topic=ev["title_hint"],
                             evidence=ev["evidence"], news_hints=None)
        kind = "flagship"
    # deterministic repairs are RECORDED, never silent: the reviewer sees every machine edit
    prov = {**prov, "normalised": fl.get("normalised") or []}
    d = qs.new_draft(kind, fl["title"], fl["body_md"], prov, fl["fidelity"],
                     ev["evidence"], trig)
    print(f"[digest]   {kind} {d['id']} -> {d['status']} ({len(fl['body_md'].split())} words)")

    # chart: deterministic, and only when the session actually had a crossing to chart
    try:
        from content_agent.charts import chart_digest_distribution
        # horizon follows the piece's spine: 5 sessions since the 2026-07-27 bake-off/held-out result
        # moved the primary horizon there (digest_core.SPINE_HORIZON). The chart must show the same
        # distribution the prose leads with.
        c = chart_digest_distribution(ev["digest"], horizon=5)
        if c:
            rec_path = qs.QUEUE / f"{d['id']}.json"
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
            rec["chart"] = c
            rec_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
            print(f"[digest]   chart -> {Path(c['path']).name}")
        else:
            print("[digest]   no crossing this session — no distribution chart (correct, not a failure)")
    except Exception as e:
        print(f"[digest]   chart failed ({type(e).__name__}: {e}) — draft stands without it")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", action="store_true")
    ap.add_argument("--study", default=None)
    ap.add_argument("--topic", default=None, help="editorial framing override for the flagship")
    ap.add_argument("--skip-notes", action="store_true")
    ap.add_argument("--notes-only", action="store_true")
    ap.add_argument("--max-notes", type=int, default=None,
                    help="cap notes for this run (default: drafting.notes_per_flagship)")
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

    # ============================ THE DAILY MEASURED DIGEST (D1) ============================
    # Runs FIRST and on its OWN gate, before study drafting, because it is the session-dated piece:
    # it is worth nothing tomorrow, whereas a study piece is worth the same whenever it is drafted.
    #
    # ORDERING IS THE WHOLE POINT — refresh, VERIFY, then generate:
    #   1. refresh the Yahoo substrate (session-gated: a bar dated today is stored only after the
    #      close, so an intraday run stores nothing rather than storing a provisional number);
    #   2. re-check every series against its staleness tolerance;
    #   3. ONLY THEN generate. If ANY series is stale the digest DOES NOT RUN this session.
    # A digest built on stale prices is worse than no digest: it prints last week's close as today's
    # move, with full confidence and every honesty label intact. Silence is the honest failure mode,
    # and the refusal is logged so a run of quiet days is visible rather than mysterious.
    if CFG.get("digest", {}).get("enabled") and not args.study and not args.notes_only:
        _run_digest(args)

    st = qs.load_state()
    if args.study:
        # EXPLICIT human request overrides the dedup guards — they exist to stop the AUTOMATION from
        # looping, never to refuse a person who asked for a specific study by name.
        trig = {"trigger": "manual", "study_id": args.study,
                "topic": args.topic or "manual/launch draft"}
        print(f"[daily] trigger: manual -> {trig['study_id']} (guards bypassed: explicit request)")
    else:
        trig = _select_trigger(st)
        if trig is None:
            return
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
        # SAME RECORD ON THIS PATH. The deterministic repairs happen inside draft_flagship for any
        # digest-class evidence, so a digest generated via --study got its title rewritten and its
        # heading inserted but carried no record of it — the reviewer could not see the machine's
        # edits on that path. Recorded here too; empty for every non-digest study.
        prov_f = {**prov, "normalised": fl.get("normalised") or []}
        d = qs.new_draft("flagship", fl["title"], fl["body_md"], prov_f, fl["fidelity"], ev_check, trig)
        print(f"[daily]   flagship {d['id']} -> {d['status']}")
        _commit_override_state(trig, st, d)
        # CHART ATTACH, class-routed (2026-07-29): pair FLAGSHIPS get the regime-fingerprint chart,
        # the same automatic path event/recovery classes have. Notes stay text-only by design — a
        # 40-130-word note is a single claim, and a chart beside it competes with the claim rather
        # than carrying it. Failure is non-fatal: the draft stands without the picture.
        if trig["study_id"].startswith("pair:"):
            try:
                from content_agent.charts import chart_pair_regimes
                c = chart_pair_regimes(trig["study_id"].split(":", 1)[1])
                if c:
                    rec_path = qs.QUEUE / f"{d['id']}.json"
                    rec = json.loads(rec_path.read_text(encoding="utf-8"))
                    rec["chart"] = c
                    rec_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
                    print(f"[daily]   chart -> {Path(c['path']).name} ({c['n_bars']} bars"
                          f"{', crosses zero' if c['crosses_zero'] else ''})")
                else:
                    print("[daily]   pair has <2 measured episodes — no chart (correct, not a failure)")
            except Exception as e:                   # noqa: BLE001
                print(f"[daily]   chart failed ({type(e).__name__}: {e}) — draft stands without it")

    if not args.skip_notes:
        n_notes = args.max_notes if args.max_notes is not None else CFG["drafting"]["notes_per_flagship"]
        for focus in _note_focuses(trig["study_id"])[:n_notes]:
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
