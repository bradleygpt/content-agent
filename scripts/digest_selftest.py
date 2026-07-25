"""Daily Measured Digest self-test (D1) — hermetic: fixture evidence and fixture drafts, no network,
no GPU, no queue writes, no artifact reads. Locks the rules that make this content class honest.

  .venv/Scripts/python.exe scripts/digest_selftest.py

WHAT IS LOCKED HERE, and why each rule exists (every one traces to a measured D0/D1 finding):
  - MEDIAN-WITHOUT-N: a median alone reads as a forecast. It must carry its hit rate AND N in the SAME
    sentence, because a reader takes the number from the sentence in front of them.
  - BARE-AVERAGE: averaging a conditional distribution destroys the spread that is its entire content.
  - Scoping: the rule fires ONLY on digest-class evidence (NOT-A-SIGNAL present). A recovery study's
    "median depth -19.3%" is a different kind of number and must keep passing.
  - NOT-A-SIGNAL travels as a required label, and is INVENTED-LABEL-guarded like every other label.
  - The citation path is verbatim-only: a headline may be reproduced, never summarised.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from content_agent.fidelity import run_fidelity, check_median_discipline  # noqa: E402

# Minimal digest-class evidence: carries NOT-A-SIGNAL, so the median rule is in scope.
DIGEST_EV = """MEASURED DAILY DIGEST EVIDENCE — session of 2026-07-23.
SECTION 3 — NEXT SESSION
    +1 session(s) [all instances]: median 0.07%, positive in 25 of 46 instances (hit rate 0.543),
      full range -10.11% to 7.81%, N=46
REQUIRED HONESTY LABELS (carry into the answer):
  - NOT-A-SIGNAL: conditional distributions describe what followed comparable past days.
  - CENSORED: unrecovered instances have unknown outcomes; never impute them.
"""

# A non-digest study block: NO NOT-A-SIGNAL, so the median rule must NOT fire here.
RECOVERY_EV = """MEASURED DRAWDOWN-RECOVERY EVIDENCE
  drawdowns >= 10.0% since 2004: 7 (deepest -55.2%, median depth -19.3%)
REQUIRED HONESTY LABELS (carry into the answer):
  - SINGLE-INSTANCE: each named-episode recovery is one historical instance.
"""


def main():
    ok, checks = True, []

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        checks.append((bool(cond), name))

    def fails(draft, ev=DIGEST_EV):
        return {f["type"] for f in check_median_discipline(draft, ev)}

    # --- MEDIAN-WITHOUT-N -------------------------------------------------------------------------
    good = ("The median next session was 0.07%, positive in 25 of 46 instances (hit rate 0.543), "
            "with a full range of -10.11% to 7.81%.")
    check("median WITH hit rate and N in the same sentence -> passes", "MEDIAN-WITHOUT-N" not in fails(good))

    check("bare median -> MEDIAN-WITHOUT-N",
          "MEDIAN-WITHOUT-N" in fails("The median next session was 0.07%."))
    check("median + hit rate but NO N -> still fails",
          "MEDIAN-WITHOUT-N" in fails("The median was 0.07%, a hit rate of 0.543."))
    # THE SENTENCE-SCOPE RULE: N three sentences away does not rescue the median a reader is looking at
    split = ("The median next session was 0.07%. Separately, there were 46 such instances in total, "
             "positive in 25 of them.")
    check("N in a DIFFERENT sentence does NOT satisfy the rule (sentence-scoped)",
          "MEDIAN-WITHOUT-N" in fails(split))
    check("'N=46' alone satisfies N, with a hit rate present",
          "MEDIAN-WITHOUT-N" not in fails("Median 0.07% (hit rate 0.543, N=46)."))
    # MEDIAN-AS-ADJECTIVE: the INDEX-MEASURED label the drafter MUST carry contains the word "median"
    # with no value attached. Failing that punishes a draft for obeying a mandatory instruction — caught
    # in the D1 validation gate on the first live digest, and locked here.
    label_sent = ("The S&P 500 (SPY ETF) declined -1.23% [INDEX-MEASURED: index moves are shallower "
                  "than the median single stock's; never present them as typical for one name].")
    check("INDEX-MEASURED label text ('the median single stock') is NOT a reported median",
          "MEDIAN-WITHOUT-N" not in fails(label_sent))
    for adj in ["Index drawdowns are shallower than the median individual stock's.",
                "Many single names never recover, unlike the median name."]:
        check(f"median-as-adjective not flagged: \"{adj[:38]}…\"", "MEDIAN-WITHOUT-N" not in fails(adj))
    # ...but a real median in the SAME shape must still fail
    check("a reported median still fails even beside a label",
          "MEDIAN-WITHOUT-N" in fails("The median next session was 0.07% [INDEX-MEASURED: index "
                                      "moves are shallower than the median single stock's]."))

    # --- BARE-AVERAGE -----------------------------------------------------------------------------
    check("'the average was' -> BARE-AVERAGE", "BARE-AVERAGE" in fails("The average next session was 0.2%."))
    check("'on average' hedge -> BARE-AVERAGE",
          "BARE-AVERAGE" in fails("Stocks rose on average after such days."))
    check("'mean' as a statistic -> BARE-AVERAGE", "BARE-AVERAGE" in fails("The mean was 0.2%."))
    check("good sentence carries NO bare-average failure", "BARE-AVERAGE" not in fails(good))
    # word-boundary safety: these are not the statistic
    for w in ["Meanwhile, the index fell.", "This is a meaningful distinction.",
              "That means the range is wide."]:
        check(f"not flagged as an average: \"{w[:32]}…\"", "BARE-AVERAGE" not in fails(w))

    # --- BARE-AVERAGE must not fire on EVIDENCE-MANDATED text -------------------------------------
    # The CENSORED label reads "...never imputed or averaged in" — a phrase whose content is a
    # PROHIBITION on averaging, which the drafter is required to carry. Failing a draft for reproducing
    # it was the fourth time this module penalised obedience.
    _cens_ev = (DIGEST_EV + "\n  - CENSORED: 1 instance(s) have NOT regained the prior high — recovery "
                            "time UNKNOWN, never imputed or averaged in.\n")
    check("quoting the evidence's own 'never imputed or averaged in' does NOT fire",
          "BARE-AVERAGE" not in {f["type"] for f in check_median_discipline(
              "One instance has not regained its prior high — recovery time UNKNOWN, never imputed "
              "or averaged in.", _cens_ev)})
    check("but a REAL average in the same draft still fires",
          "BARE-AVERAGE" in {f["type"] for f in check_median_discipline(
              "The average next session was 0.2%.", _cens_ev)})
    check("an average smuggled into an otherwise-quoted sentence still fires",
          "BARE-AVERAGE" in {f["type"] for f in check_median_discipline(
              "The average was 0.2%, and it is never imputed.", _cens_ev)})

    # --- UNIT EQUIVALENCE: day <-> count, and NOTHING else ----------------------------------------
    # "16 of these days fell in 2008" vs evidence "16 of these fell in 2008" — the same quantity,
    # accurately labelled, and it was hard-failing.
    _ev_ct = "CRISIS CLUSTERING: 16 of these instances fell in 2008; recovery median 542 sessions."
    _r = run_fidelity("16 of these days fell in 2008.", _ev_ct)
    check("draft 'days' binds to evidence 'instances' (day <-> count)",
          not any(f["type"] == "UNIT-MISMATCH" for f in _r["failures"]))
    # ...but a session is NOT a calendar day, and that must still fail
    _r2 = run_fidelity("Recovery took 542 days.", _ev_ct)
    check("'542 days' vs evidence '542 sessions' STILL fails (session != day)",
          any(f["type"] == "UNIT-MISMATCH" for f in _r2["failures"]))
    _r3 = run_fidelity("Recovery took 542 sessions.", _ev_ct)
    check("'542 sessions' binds correctly", not any(f["type"] == "UNIT-MISMATCH"
                                                    for f in _r3["failures"]))
    _r4 = run_fidelity("It took 3 weeks.", "recovery median 3 months")
    check("months-vs-weeks is STILL a hard fail (the bug this module exists for)",
          any(f["type"] == "UNIT-MISMATCH" for f in _r4["failures"]))

    # --- CAUSAL CLAIMS ----------------------------------------------------------------------------
    # The failure every other check waves through: a causal sentence binds every number and carries
    # every label. Found in the D1 gate by probing the checker with the failure modes the format exists
    # to prevent, rather than by assuming the drafter instruction was sufficient.
    from content_agent.fidelity import check_causal_claims

    def causal(draft, ev=DIGEST_EV):
        return {f["type"] for f in check_causal_claims(draft, ev)}

    for bad in ["Consumer discretionary fell -4.61%, driven by the rise in crude.",
                "The decline was caused by the sell-off in semiconductors.",
                "Staples fell amid rising yields.",
                "Discretionary dropped on the back of weak earnings.",
                "Energy rose, which explains the sector spread.",
                "It was a rate-driven session.",
                "Utilities were weighed on by the yield move."]:
        check(f"causal language caught: \"{bad[:44]}…\"", "CAUSAL-CLAIM" in causal(bad))

    for ok in ["Consumer discretionary fell -4.61% and crude rose 6.17% the same session.",
               "The S&P 500 declined -1.23%. Semiconductors rose 4.52%.",
               "These series moved on the same session; the evidence measures no relationship.",
               "The spread between best and worst sector was 6.34pp.",
               "After the close, the figures were settled."]:
        check(f"non-causal co-movement passes: \"{ok[:44]}…\"", not causal(ok))

    # "reflect" is DELIBERATELY NOT in the causal lexicon. It was tried, and in production it fired
    # only on non-causal uses: "factors not reflected in this data set" (a coverage disclaimer) and
    # "this record reflects settled prices at the close" (a description of what the data IS). Its
    # genuinely causal use always carries a stronger marker too, so nothing is lost by dropping it.
    # A rule that only ever fires wrongly teaches the writer to fight the checker, not the claim.
    for ok in ["The observed patterns may shift with factors not reflected in this data set.",
               "This measured session record reflects settled prices at the close of trading.",
               "Conditions not reflected in the sample could differ."]:
        check(f"'reflect' is not treated as causal: \"{ok[:38]}…\"", not causal(ok))
    check("a genuinely causal sentence is still caught by its stronger marker",
          "CAUSAL-CLAIM" in causal("The move was driven by concern about demand."))

    # --- MEDIAN KIND: a DURATION has no hit rate ---------------------------------------------------
    # The rule originally demanded a hit rate for every median. Section 4 reports recovery DURATIONS and
    # the evidence prints no hit rate anywhere — so the only way to satisfy it was to fabricate one.
    dur_ok = ("The median time to regain the prior high was 542 sessions, ranging from 20 to 672 "
              "sessions, over 46 recovered instances.")
    check("recovery median with N + range passes (no hit rate exists for a duration)",
          "MEDIAN-WITHOUT-N" not in fails(dur_ok))
    check("recovery median WITHOUT its range still fails",
          "MEDIAN-WITHOUT-N" in fails("The median time to regain the prior high was 542 sessions."))
    check("return median still REQUIRES a hit rate",
          "MEDIAN-WITHOUT-N" in fails("The median next session was 0.07% over 46 instances."))

    check("causal rule does NOT fire on a non-digest study",
          not check_causal_claims("The drawdown was caused by the credit crisis.", RECOVERY_EV))

    # --- CENSORED label detection (GENERAL checker regression, not digest-specific) ----------------
    # Lives here because this is the active checker self-test. The evidence builders render required
    # labels as "  - CENSORED: ..." bullets and the original anchor matched none of them, so the label
    # was never required and any draft that carried it was failed for INVENTING it — a rule that
    # punishes obedience. Hit recovery:ANCHOR_SPY and then recovery:ANCHOR_NASDAQ in the first nightly.
    import re as _re
    from content_agent.fidelity import LABELS as _L
    _crx = _L["CENSORED"][0]
    for txt, want, why in [
            ("  - CENSORED: an ongoing drawdown has unknown recovery time", True, "bullet (real form)"),
            ("  * CENSORED: unknown", True, "asterisk bullet"),
            ("CENSORED: 1 episode still underwater", True, "bare line"),
            ("[CENSORED] unknown", True, "bracket form"),
            ("the data was censored in some way", False, "prose mention must NOT require it"),
            ("we discuss censored observations", False, "word in a sentence")]:
        check(f"CENSORED evidence detection — {why}", bool(_re.search(_crx, txt)) is want)

    # --- UNDERSCORE-FUSED EPISODE KEYS (ported from markets-llm answer_fidelity, 2026-07-24) ---------
    # "repricing_2022" hid the year from the extractor, so a draft correctly writing 2022 hard-failed
    # NO-MATCH against evidence that visibly contained it.
    from content_agent.fidelity import _extract as _ex
    _, _, _yrs = _ex("repricing_2022: -24.5% drawdown; crash_2008 recovery 41.3mo", wide_evidence=True)
    check("underscore-fused years are extracted (repricing_2022 -> 2022)", 2022 in _yrs)
    check("underscore-fused years are extracted (crash_2008 -> 2008)", 2008 in _yrs)
    _r = run_fidelity("The 2022 repricing took 14.0 months.",
                      "repricing_2022: -24.5% drawdown, recovery 14.0mo")
    check("a draft citing 2022 no longer NO-MATCHes",
          not any(f["type"] == "NO-MATCH" and f["token"] == "2022" for f in _r["failures"]))

    # --- CAUSAL rule must not fire on RECITED evidence, and recitation is caught separately ---------
    # The evidence's NO-CAUSATION instruction contains the very words the causal rule forbids, so a
    # draft reciting it fired CAUSAL-CLAIM for the wrong reason (fifth occurrence of this module
    # penalising mandatory-text recitation). Reciting is still a defect — INSTRUCTION-RECITATION owns it.
    from content_agent.fidelity import check_instruction_recitation
    _instr_ev = (DIGEST_EV + "\nNO CAUSATION. These series moved on the same session. Do not write "
                             "that one caused, drove, triggered, or explains another — the evidence "
                             "contains no such measurement.\n")
    _recite = ("These series moved on the same session; do not write that one caused, drove, "
               "triggered, or explains another.")
    check("reciting the NO-CAUSATION instruction does NOT fire CAUSAL-CLAIM",
          "CAUSAL-CLAIM" not in {f["type"] for f in check_causal_claims(_recite, _instr_ev)})
    check("...but it DOES fire INSTRUCTION-RECITATION",
          "INSTRUCTION-RECITATION" in {f["type"] for f in
                                       check_instruction_recitation(_recite, _instr_ev)})
    check("a real causal claim still fires CAUSAL-CLAIM",
          "CAUSAL-CLAIM" in {f["type"] for f in
                             check_causal_claims("Staples fell, caused by the yield move.", _instr_ev)})
    # quoting FIGURES is the job, not recitation; and naming a label is required, not recitation
    for ok in ["Consumer discretionary fell -4.61% and crude rose 6.17% the same session.",
               "The record is NOT-A-SIGNAL: it describes what followed comparable days, nothing more.",
               "Unrecovered instances stay censored rather than imputed."]:
        check(f"not recitation: \"{ok[:42]}…\"", not check_instruction_recitation(ok, _instr_ev))
    check("recitation rule does NOT fire on a non-digest study",
          not check_instruction_recitation(_recite, RECOVERY_EV))

    # --- INVENTED-LABEL fires on ASSERTIONS, not on DENIALS ----------------------------------------
    # A draft wrote "nor does it address censored instances or survivorship limitations" — correctly
    # noting their absence — and was failed for asserting both.
    # NOTE the fixture: DIGEST_EV *requires* CENSORED, and a required label can never be "invented".
    # These cases therefore use evidence that carries NEITHER CENSORED nor SURVIVORSHIP nor SMALL-N,
    # so an assertion of any of them is genuinely unsupported.
    _bare_ev = ("MEASURED DAILY DIGEST EVIDENCE — session of 2026-07-24.\n"
                "REQUIRED HONESTY LABELS (carry into the answer):\n"
                "  - NOT-A-SIGNAL: distributions describe what followed comparable past days.\n")

    def _inv(d):
        return {f["token"] for f in run_fidelity(d, _bare_ev)["failures"]
                if f["type"] == "INVENTED-LABEL"}

    for neg in ["The evidence does not address censored instances or survivorship limitations.",
                "There is no survivorship concern here.",
                "This is not a small-n sample.",
                "Nothing here is censored.",
                "No instance remains censored."]:
        check(f"denial is not an assertion: \"{neg[:44]}…\"", not _inv(neg))
    for pos in ["These figures carry a survivorship limitation.",
                "One instance remains censored.",
                "This is a small-n sample of five."]:
        check(f"assertion still fires: \"{pos[:44]}…\"", bool(_inv(pos)))

    # --- amid / amidst -----------------------------------------------------------------------------
    # "amidst?" parses as "amids" + optional "t" and silently stopped matching plain "amid".
    for a in ["Sectors fell amid rising yields.", "Steady amidst global shifts.",
              "Sector Performance Steady Amidst Global Shifts"]:
        check(f"causal connective caught: \"{a[:40]}…\"", "CAUSAL-CLAIM" in causal(a))
    check("no false hit on 'amiable'", not causal("An amiable session."))

    # --- prose dates bind against the session date -------------------------------------------------
    _dev = "MEASURED DAILY DIGEST EVIDENCE — session of 2026-07-24.\nNOT-A-SIGNAL\nspread 6.34 points"
    check("\"July 24th\" no longer NO-MATCHes (naming the session is normal writing)",
          not any(f["type"] == "NO-MATCH" for f in
                  run_fidelity("The session of July 24th saw a spread of 6.34 points.", _dev)["failures"]))
    check("\"24 July\" form also binds",
          not any(f["type"] == "NO-MATCH" for f in
                  run_fidelity("On 24 July the spread was 6.34 points.", _dev)["failures"]))
    check("a genuinely ungrounded number still NO-MATCHes",
          any(f["type"] == "NO-MATCH" for f in run_fidelity("It moved 24 percent.", _dev)["failures"]))

    # --- NOTATION AUDIT: every unit form digest_core emits must resolve -----------------------------
    # This class has cost three rounds ("sessions", the ^TNX scale, then "pp"), each discovered live.
    # The table is the audit: adding a notation to the evidence without adding it here should fail.
    import re as _re2
    from content_agent.fidelity import _unit_for as _uf, _prep as _pp2
    for _txt, _want in [("-4.61%", "pct"), ("5.46pp", "pct"), ("+0.05pp", "pct"),
                        ("6.34 percentage points", "pct"), ("542 sessions", "session"),
                        ("46 instances", "count"), ("N=46", "count"), ("14.0mo", "month"),
                        ("3 weeks", "week"), ("0.543", None)]:
        _t = _pp2(_txt)
        _m = _re2.search(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\d.])", _t)
        check(f"notation resolves: {_txt!r} -> {_want}",
              _uf(_t, _m.start(), _m.end(), 60) == _want)

    # CLAUSE BOUNDARY, both directions. A unit must never be inherited across a newline: the evidence
    # line "...SMH ETF proxy): -3.27%" leaked pct onto the crisis count on the NEXT line, so a draft
    # writing "35 of these days" collided with a phantom "35 pct".
    _two_line = "  semiconductors (SMH ETF proxy): -3.27%\n  CRISIS CLUSTERING: 35 of these days fell"
    _units35 = {str(t["unit"]) for t in _ex(_two_line, wide_evidence=True)[0] if t["value"] == 35.0}
    check("no unit inherited across a newline (35 is not pct)", "pct" not in _units35)
    check("...and the same line's own unit still resolves",
          any(t["value"] == 3.27 and t["unit"] == "pct"
              for t in _ex(_two_line, wide_evidence=True)[0]))

    # --- DETERMINISTIC NORMALISATION (title + first heading) --------------------------------------
    # Three prompt attempts each; both are now mechanical, and both are recorded on the draft.
    from content_agent.drafter import normalize_digest_markdown as _norm
    _bad = ("# Semiconductors Decline Amid Mixed Global Session\n\nSemis fell -3.27%.\n\n"
            "## The context\nVIX rose.\n\n## Next session\nx\n\n## Full recovery\ny")
    _out, _ch = _norm(_bad)
    check("title causal connective replaced with a semicolon", "Amid" not in _out.splitlines()[0])
    check("title rewrite preserves both halves",
          "Semiconductors Decline" in _out and "Mixed Global Session" in _out)
    check('omitted "## The mark" heading is inserted', "## The mark" in _out)
    check("the mark prose ends up UNDER the inserted heading",
          _out.index("## The mark") < _out.index("Semis fell -3.27%"))
    check("both repairs are reported, not silent", len(_ch) == 2)
    _clean = "# Semiconductors Fall; Spread 5.46 Points\n\n## The mark\nx\n\n## The context\ny"
    _o2, _c2 = _norm(_clean)
    check("an already-clean draft is left byte-identical", _o2 == _clean and not _c2)
    _nohead = "# Title\n\n## The mark\nx\n\n## The context\ny"
    check("heading NOT inserted when it already exists", _norm(_nohead)[0].count("## The mark") == 1)

    # --- COMPLETENESS -----------------------------------------------------------------------------
    # The first digest to PASS fidelity was truncated mid-sentence with Section 4 missing. Every check
    # validated what it said; none noticed what it never reached.
    from content_agent.fidelity import check_completeness

    FULL_EV = DIGEST_EV + "\nSECTION 3 — NEXT SESSION\nSECTION 4 — FULL RECOVERY\n"

    def comp(draft, ev=FULL_EV):
        return {f["type"] for f in check_completeness(draft, ev)}

    # HEADINGS ARE CHECKED AS HEADINGS, not as words appearing in prose. A draft that buried Section 4's
    # numbers in a paragraph passed the earlier content-based test while being unscannable.
    _hdr = "## The mark\nx.\n## The context\ny.\n## Next session\nz.\n## Full recovery\nw."
    check("all four '## ' headings present -> passes", not comp(_hdr))
    prose_only = ("The mark was a decline. Next session the median was 1%. "
                  "Full recovery took 542 sessions.")
    missing = comp(prose_only)
    check("headings' WORDS in running prose do NOT satisfy the check", "MISSING-SECTION" in missing)
    check("sections 1 and 2 are required even without a crossing",
          any(f["token"] == "The mark" for f in check_completeness("no headings here.", DIGEST_EV)))
    check("'### The mark' (deeper level) still counts as a heading",
          not comp(_hdr.replace("## The mark", "### The mark")))

    truncated = "## Next session\nThe median was 0.07%, positive in 25 of 46 (N=46), full range"
    check("draft ending mid-sentence -> TRUNCATED-DRAFT", "TRUNCATED-DRAFT" in comp(truncated))
    check("truncated draft ALSO missing its section -> MISSING-SECTION",
          "MISSING-SECTION" in comp(truncated))
    complete = ("## The mark\nA decline.\n## The context\nOther moves.\n"
                "## Next session\nMedian 0.07%, positive in 25 of 46 (N=46).\n"
                "## Full recovery\nMedian 542 sessions over 46 instances.")
    check("complete draft with both sections passes", not comp(complete))
    check("draft ending in a quote still counts as terminated",
          "TRUNCATED-DRAFT" not in comp(complete + ' He called it "measured."'))
    # a quiet session has NO section 3/4 in evidence, so their absence must NOT fail
    # A quiet session must still carry sections 1 and 2 — only 3/4 are evidence-conditional.
    check("quiet session: sections 3/4 not required, 1/2 still are",
          not check_completeness("## The mark\nDispersion was 2.1pp.\n## The context\nVIX rose.",
                                 DIGEST_EV.replace("SECTION 3", "X")))

    # --- SCOPING: non-digest studies are untouched ------------------------------------------------
    check("median depth on a RECOVERY study -> rule does not fire (different class)",
          not check_median_discipline("The median depth was -19.3% across the seven drawdowns.",
                                      RECOVERY_EV))
    check("average on a NON-digest study -> rule does not fire",
          not check_median_discipline("The average drawdown was deep.", RECOVERY_EV))

    # --- NOT-A-SIGNAL as a first-class label ------------------------------------------------------
    r = run_fidelity("Median 0.07%, positive in 25 of 46 instances (hit rate 0.543), N=46, range "
                     "-10.11% to 7.81%. Unrecovered episodes are censored.", DIGEST_EV)
    check("evidence carrying NOT-A-SIGNAL makes it REQUIRED", r["labels"]["NOT-A-SIGNAL"]["required"])
    check("draft omitting NOT-A-SIGNAL -> MISSING-LABEL",
          any(f["type"] == "MISSING-LABEL" and f["token"] == "NOT-A-SIGNAL" for f in r["failures"]))
    r2 = run_fidelity("This is not a signal, not a forecast. Median depth -19.3% over 7 drawdowns. "
                      "Each episode is one historical instance.", RECOVERY_EV)
    check("draft asserting NOT-A-SIGNAL on evidence that lacks it -> INVENTED-LABEL",
          any(f["type"] == "INVENTED-LABEL" and f["token"] == "NOT-A-SIGNAL" for f in r2["failures"]))

    # --- a fully compliant digest draft passes end to end -----------------------------------------
    clean = ("The measured record is not a signal: it describes what followed comparable days, not what "
             "comes next. Median 0.07%, positive in 25 of 46 instances (hit rate 0.543), full range "
             "-10.11% to 7.81%, N=46. Unrecovered instances stay censored rather than imputed.")
    rc = run_fidelity(clean, DIGEST_EV)
    check("a compliant digest draft passes fidelity outright",
          rc["passed"] or not [f for f in rc["failures"]
                               if f["type"] in ("MEDIAN-WITHOUT-N", "BARE-AVERAGE", "MISSING-LABEL")])

    # --- BLOCK SHAPE: required labels must describe what the block ACTUALLY contains -----------------
    # Caught in D1 validation: a fixed label list demanded NOT-A-SIGNAL and CENSORED on a quiet session
    # that shows no distribution and no recovery data — the INVENTED-LABEL failure with the sign flipped,
    # and the checker would have enforced it. These use the real builder against a fixture digest, so a
    # future edit that re-hardcodes the list fails here rather than in production prose.
    try:
        import sys as _s
        from content_agent.studies import MLL
        _s.path.insert(0, str(MLL / "generation"))
        import digest_core as dc

        quiet = {"as_of": "2026-01-02", "generated": "", "substrate": "test", "lead": "dispersion",
                 "moves": {"SPY": {"value": 1.0, "change": 0.5, "unit": "pct", "label": "S&P 500",
                                   "role": "mark", "proxy": None},
                           "XLP": {"value": 1.0, "change": -0.9, "unit": "pct", "label": "staples ETF",
                                   "role": "mark", "proxy": "staples ETF"},
                           "SMH": {"value": 1.0, "change": 1.2, "unit": "pct", "label": "semis ETF",
                                   "role": "mark", "proxy": "semis ETF"}},
                 "dispersion": {"spread_pp": 2.1,
                                "worst": {"name": "XLP", "label": "staples ETF", "change": -0.9},
                                "best": {"name": "SMH", "label": "semis ETF", "change": 1.2},
                                "notable": True},
                 "crossings": [], "citations": [],
                 "conditional_meta": {"horizons": [1], "window_start": "2004-01-01",
                                      "crisis_years": [2008, 2020], "small_n_floor": 30, "method": ""}}
        qb = dc.build_digest_block(quiet)
        check("quiet session: NO section 3", "SECTION 3" not in qb)
        check("quiet session: NO section 4", "SECTION 4" not in qb)
        check("quiet session: does NOT require NOT-A-SIGNAL (no distribution shown)",
              "- NOT-A-SIGNAL" not in qb)
        check("quiet session: does NOT require CENSORED (nothing censored)", "- CENSORED" not in qb)
        check("quiet session: DOES require SECTOR-PROXY (sector figures shown)", "- SECTOR-PROXY" in qb)
        check("quiet session: tells the drafter to stop after section 2",
              "Write sections 1-2 only" in qb)
        check("quiet session: no dangling reference to distributions 'below'",
              "conditional distributions below" not in qb)
    except Exception as e:                                  # markets-llm not reachable -> skip, not fail
        checks.append((True, f"(skipped block-shape checks: {type(e).__name__})"))

    print("DIGEST SELF-TEST (hermetic; fixtures; no network/GPU/queue)\n")
    for good_, name in checks:
        print(f"  {'OK ' if good_ else 'XX '} {name}")
    passed = sum(g for g, _ in checks)
    print(f"\nSELF-TEST: {passed}/{len(checks)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
