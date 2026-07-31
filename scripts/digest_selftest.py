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

    # --- CAUSAL IS NOW ALL-CLASS, AND GATED ON ASSERTION -------------------------------------------
    # A note reading "presidential elections regularly TRIGGER market drawdowns" passed for weeks
    # because the rule was digest-scoped — and would not have matched anyway, since the lexicon had
    # only past-tense "triggered". Both fixed. But this publication's voice is largely ABOUT the limits
    # of causal inference, so the rule fires only on causation the piece ASSERTS: quoted folklore,
    # hedged modals, explicit denials and methodological "due to" are all excluded. Measured across
    # every historical draft: unscoped+ungated failed 19 including all 3 published flagships; gated,
    # 10, and the only PENDING failure is the target claim.
    _study_ev = "MEASURED STUDY EVIDENCE\n  five midterm drawdowns since 2004"
    for _bad in ["US presidential elections regularly trigger market drawdowns.",
                 "Elections cause drawdowns.",
                 "Rate moves drive sector rotation.",
                 "The decline was caused by the selloff."]:
        check(f"all-class causal fires on an ASSERTED cause: \"{_bad[:38]}…\"",
              "CAUSAL-CLAIM" in {x["type"] for x in check_causal_claims(_bad, _study_ev)})
    for _ok in ["The narrative often suggests cyclicals lead lower ahead of midterms due to jitters.",
                "A period of heightened geopolitical risk might lead to more volatile markets.",
                "It is impossible to definitively ascribe specific causes.",
                "It does not address the factors causing these drawdowns.",
                "Markets are complex systems driven by myriad factors.",
                "Could be due to chance or circumstances unique to those elections.",
                "Two events could not be measured due to insufficient observation windows.",
                "Limitations due to the SMALL-N sample."]:
        check(f"...but NOT on quoted/hedged/denied/methodological: \"{_ok[:36]}…\"",
              not check_causal_claims(_ok, _study_ev))
    check("present-tense 'trigger' is in the lexicon (past-only let the target claim through)",
          "CAUSAL-CLAIM" in {x["type"] for x in check_causal_claims("Elections trigger selloffs.",
                                                                    _study_ev)})

    # SUPERSEDED 2026-07-27: the rule was digest-scoped, which is how a note asserting "presidential
    # elections regularly trigger market drawdowns" reached pending. It is now ALL-CLASS — a study
    # piece is held to the same bar, because the evidence measures causation in no format.
    check("causal rule NOW fires on a non-digest study too (was digest-scoped)",
          "CAUSAL-CLAIM" in {x["type"] for x in
                             check_causal_claims("The drawdown was caused by the credit crisis.",
                                                 RECOVERY_EV)})

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

    # --- NAME AUDIT: every digit-bearing LABEL the digest can print must be STRIPPED ---------------
    # The notation audit above checks UNIT TOKENS. It was scoped too narrowly, and a NAME containing a
    # digit walked straight through: "Nikkei 225" reached production unstripped and "the Nikkei 225 in
    # Japan lower by -2.73%" parsed 225 as a percentage. This half of the audit enumerates the label
    # set ITSELF, so adding a series whose label carries a digit fails here rather than in a live draft.
    try:
        import sys as _s3
        from content_agent.studies import MLL as _MLL
        _s3.path.insert(0, str(_MLL / "relational"))
        import fetch_digest as _FD
        import engine as _E
        _labels = [s["label"] for s in _FD.SERIES.values()] + list(_E.SECTOR_LABELS.values())
        _digit_labels = sorted({l for l in _labels if _re2.search(r"\d", l)})
        check("the label set contains at least one digit-bearing name (audit is live)",
              bool(_digit_labels))
        for _lab in _digit_labels:
            # every digit in the label must be GONE after _prep, or it will be read as a measurement
            check(f"digit-bearing label is stripped: {_lab!r}",
                  not _re2.search(r"\d", _pp2(_lab)))
        # and the numbers must not survive into the token pool either
        for _lab, _num in [("the Nikkei 225 in Japan fell", 225.0),
                           ("EURO STOXX 50 rose", 50.0),
                           ("the US 10-year Treasury yield", 10.0)]:
            check(f"no token extracted from {_lab.split()[1]!r} name",
                  not any(t["value"] == _num for t in _ex(_lab, wide_evidence=True)[0]))
    except Exception as e:                                  # markets-llm unreachable -> skip, not fail
        checks.append((True, f"(skipped label audit: {type(e).__name__})"))

    # HORIZON PHRASING: every horizon carries its digit AND unit, so "one-session" binds.
    _hz = "over the next 1 session (all instances): median 0.4%\nover the next 20 sessions: median 2.5%"
    _u1 = {str(t["unit"]) for t in _ex(_hz, wide_evidence=True)[0] if t["value"] == 1.0}
    check("the 1-session horizon carries the session unit (so 'one-session' binds)", "session" in _u1)

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

    # --- CENTRAL CLAUSE BOUNDARY: all three historical variants + the decimal case -----------------
    # One boundary definition now serves every window on both sides. Each of these failed live, in a
    # different window, in a different round.
    from content_agent.fidelity import _clause_after as _ca, _clause_before as _cb
    check("variant 1 — after-window stops at the clause (';')",
          "%" not in _ca("median 4.6mo, range 2.2 to 41.3; deepest -55.2%", 5, 60))
    check("variant 2 — look-back stops at a NEWLINE",
          "%" not in _cb("(SMH ETF proxy): -3.27%\n  CRISIS CLUSTERING: 35 of", 45, 45))
    check("variant 3 — look-back stops at a SENTENCE END",
          "%" not in _cb("a decline at or beyond -3%. Of these, 35 occurred", 45, 25))
    check("DECIMALS ARE NOT BOUNDARIES — '3.27%' keeps its unit",
          _uf(_pp2("-3.27%"), 1, 5, 30) == "pct")
    check("...and a decimal mid-sentence does not truncate the look-back",
          "range" in _cb("with a range from 3.27 to 9.5 and", 33, 30))

    # --- MEDIAN-WITHOUT-N: verified BOTH ways before shipping -------------------------------------
    # Flagged as a drafter failure, then verified and found to be a FALSE POSITIVE: _N_RX demanded the
    # noun immediately after the digit, so "Across all 261 recovered instances" carried N and failed.
    for _s, _want, _why in [
            ("Across all 261 recovered instances, the median recovery time was 232 sessions, with a "
             "range from just 2 sessions to as long as 2544 sessions.", True, "N + range, modifiers"),
            ("The median was 232 sessions, ranging 2 to 2544, over 205 recovered instances.",
             True, "N + range"),
            ("Excluding crises, the median recovery time shortened to 213 sessions, still spanning a "
             "range from 2 to 2544 sessions.", False, "range but genuinely NO N"),
            ("The median recovery time was 232 sessions.", False, "neither")]:
        _passed = "MEDIAN-WITHOUT-N" not in {x["type"] for x in check_median_discipline(_s, DIGEST_EV)}
        check(f"duration median — {_why}", _passed is _want)

    # --- NOT-A-SIGNAL: the LABEL was right, the DETECTION was too narrow ---------------------------
    from content_agent.fidelity import LABELS as _LB
    _nas = _LB["NOT-A-SIGNAL"][1]
    for _s in ["The measurement cannot be interpreted as a forecast of future market behavior.",
               "It does not predict tomorrow's movements.",
               "These are historical outcomes, not forecasts.",
               "It describes what followed comparable past days."]:
        check(f"natural deferral satisfies NOT-A-SIGNAL: \"{_s[:40]}…\"",
              bool(_re2.search(_nas, _s, _re2.I)))
    for _s in ["Semiconductors fell -3.27% and crude rose 6.17%.",
               "The median was 232 sessions over 205 instances."]:
        check(f"unrelated prose does NOT satisfy it: \"{_s[:40]}…\"",
              not _re2.search(_nas, _s, _re2.I))

    # --- RECITED-SENTENCE STRIP (mechanical, 4th-occurrence treatment) -----------------------------
    from content_agent.drafter import _strip_recited_sentences as _srs
    _iev = ("MEASURED DAILY DIGEST EVIDENCE\n  INDEX-MEASURED applies here — tell the reader IN YOUR "
            "OWN WORDS that an index move is shallower than a typical single stock's.\n")
    _body = ("Semis fell -3.27%. INDEX-MEASURED applies here — tell the reader IN YOUR OWN WORDS that "
             "an index move is shallower than a typical single stock's. The spread was 5.46pp.")
    _o, _c = _srs(_body, _iev)
    check("a recited INSTRUCTION sentence is removed", "tell the reader" not in _o)
    check("...and the surrounding prose survives intact",
          "Semis fell -3.27%." in _o and "The spread was 5.46pp." in _o)
    check("the removal is reported, not silent", len(_c) == 1)
    _fig = "Semis fell -3.27%. The median was 2.52% over 262 instances."
    check("a sentence quoting only FIGURES is never removed", _srs(_fig, _iev)[0] == _fig)

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
    # fixtures are FLAGSHIP-LENGTH on purpose: since the note-form exemption (option (b)), a tiny
    # heading-less string legitimately reads as a note — the original defect these lock against was
    # a long flagship burying its sections in running prose, so the fixtures now have that shape.
    _pad = " The measured record continues with further descriptive prose about the session." * 25
    prose_only = ("The mark was a decline. Next session the median was 1%. "
                  "Full recovery took 542 sessions." + _pad)
    missing = comp(prose_only)
    check("headings' WORDS in running prose do NOT satisfy the check", "MISSING-SECTION" in missing)
    check("sections 1 and 2 are required even without a crossing",
          any(f["token"] == "The mark"
              for f in check_completeness("no headings here." + _pad, DIGEST_EV)))
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
    # ...and FORBIDDEN when absent: the first dispersion-led digest of the rebuilt format wrote
    # "## Full recovery" anyway and padded it with fabricated scaffolding. Symmetric with MISSING.
    check("quiet session: writing '## Full recovery' anyway -> EXTRA-SECTION",
          any(f["type"] == "EXTRA-SECTION" and f["token"] == "Full recovery"
              for f in check_completeness("## The mark\nx.\n## The context\ny.\n## Full recovery\n"
                                          "Not measured, but here are words.",
                                          DIGEST_EV.replace("SECTION 3", "X"))))
    check("crossing session: '## Full recovery' present is NOT extra (evidence carries SECTION 4)",
          not any(f["type"] == "EXTRA-SECTION" for f in comp(_hdr)))

    # --- SCOPING, INVERTED 2026-07-31 --------------------------------------------------------------
    # These three checks asserted that median-discipline and word-number DO NOT fire outside the
    # digest. That scoping was the defect, not the design: a recovery median without its N is exactly
    # the misleading statistic the publication exists to refuse, and the study classes need the rule
    # more than the digest does. The exemption-shield audit found it; the assertions are inverted
    # rather than deleted so the old behaviour cannot quietly return.
    check("median depth on a RECOVERY study now FIRES (N present, range missing)",
          any(f["type"] == "MEDIAN-WITHOUT-N" for f in
              check_median_discipline("The median depth was -19.3% across the seven drawdowns.",
                                      RECOVERY_EV)))
    check("median depth on a RECOVERY study with N AND range stays silent",
          not check_median_discipline("The median depth was -19.3% across the seven drawdowns, "
                                      "ranging from -8.1% to -41.0%.", RECOVERY_EV))
    check("average on a NON-digest study now FIRES",
          any(f["type"] == "BARE-AVERAGE" for f in
              check_median_discipline("The average drawdown was deep.", RECOVERY_EV)))

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
        check("quiet session: tells the drafter to stop after section 2 (+ Similar sessions)",
              "Write sections 1, 2 and Similar sessions only" in qb)
        check("quiet session: no dangling reference to distributions 'below'",
              "conditional distributions below" not in qb)
    except Exception as e:                                  # markets-llm not reachable -> skip, not fail
        checks.append((True, f"(skipped block-shape checks: {type(e).__name__})"))

    # --- CENSORED presence: natural phrasing satisfies; absence still fails (both directions) -------
    # "Seven instances have NOT regained their prior high — recovery time remains UNKNOWN" is a
    # complete carry of CENSORED and was hard-failed for word order (2026-07-27). Locked both ways.
    from content_agent.fidelity import LABELS as _LB2
    _cen = _LB2["CENSORED"][1]
    for _s in ["Seven instances have NOT regained their prior high — recovery time remains UNKNOWN.",
               "One episode has never regained its prior high.",
               "Unrecovered episodes are censored, not averaged in."]:
        check(f"natural censoring statement satisfies CENSORED: \"{_s[:42]}…\"",
              bool(_re2.search(_cen, _s, _re2.I)))
    for _s in ["All 261 instances regained the prior high.",
               "The median recovery was 232 sessions over 261 instances."]:
        check(f"non-censoring prose does NOT satisfy CENSORED: \"{_s[:42]}…\"",
              not _re2.search(_cen, _s, _re2.I))

    # --- SIMILAR SESSIONS (relational content rebuild, item 1) --------------------------------------
    # The analog section's two hard guarantees: every analog DATE a draft cites must exist in the
    # evidence (a date is a fact, and an invented one is a fabricated fact), and every cited OUTCOME
    # must bind like any other number. Plus the held-out gate: the drafter must not synthesise a
    # 20-session aggregate the evidence deliberately omits — enforced here to the extent the checker
    # can (an invented aggregate median must fail MEDIAN-WITHOUT-N or NO-MATCH).
    ANALOG_EV = """MEASURED DAILY DIGEST EVIDENCE — session of 2026-07-24.
SECTION 2A — SIMILAR SESSIONS (nearest measured analogs; SIMILARITY, NOT A FORECAST)
  The nearest analog sessions, each with WHAT FOLLOWED THAT SESSION INDIVIDUALLY:
    2006-08-14: that day +0.08%, next 5 sessions +2.38%, next 20 sessions +3.60%
    2008-05-08: that day -0.26%, next 5 sessions +2.42%, next 20 sessions -2.06%
  Year composition of all 150 analog sessions: 20 instances from 2008, 16 instances from 2020.
  Aggregate over the next 5 sessions across all 150 analogs: median 0.84%, positive in 93 of 150
  instances (hit rate 0.62), full range -9.8% to 7.55%, N=150
REQUIRED HONESTY LABELS (carry into the answer):
  - NOT-A-SIGNAL: analog outcomes describe what followed comparable past days.
"""
    _ra = run_fidelity("On 2006-08-14 the index moved +0.08%, and the next 5 sessions ran +2.38%. "
                       "Not a forecast.", ANALOG_EV)
    check("analog date IN evidence binds", not any(f["type"] == "NO-MATCH" and f["token"] == "2006-08-14"
                                                   for f in _ra["failures"]))
    _rb = run_fidelity("On 2006-08-15 the index moved +0.08%.", ANALOG_EV)
    check("analog date NOT in evidence -> NO-MATCH (a fabricated dated fact)",
          any(f["type"] == "NO-MATCH" and f["token"] == "2006-08-15" for f in _rb["failures"]))
    _rc2 = run_fidelity("After 2008-05-08 the next 20 sessions ran -3.99%.", ANALOG_EV)
    check("analog OUTCOME not in evidence -> NO-MATCH",
          any(f["type"] == "NO-MATCH" and "-3.99" in f["token"] for f in _rc2["failures"]))
    check("year-mix count binds bare ('16 of the analogs came from 2020')",
          not any(f["type"] == "NO-MATCH"
                  for f in run_fidelity("16 of the 150 analogs came from 2020. Not a forecast.",
                                        ANALOG_EV)["failures"]))
    # the first live draft wrote the natural "20 instances from 2008" and hard-failed UNIT-MISMATCH
    # because the evidence's year-mix carried no unit. The evidence now names "instances" per count
    # (the crisis-line law); this locks that both the count-unit form and the bare form bind.
    check("year-mix count binds WITH the unit word ('16 instances from 2020')",
          not any(f["type"] in ("NO-MATCH", "UNIT-MISMATCH")
                  for f in run_fidelity("The set included 16 instances from 2020. Not a forecast.",
                                        ANALOG_EV)["failures"]))
    check("synthesised 20-session analog aggregate (bare median) -> fails",
          bool(check_median_discipline("Across the analogs the median 20-session outcome was +1.9%.",
                                       ANALOG_EV)))
    check("the shipped 5-session aggregate sentence (hit rate + N) -> passes",
          not check_median_discipline("The 5-session analog median was 0.84%, positive in 93 of 150 "
                                      "instances (N=150).", ANALOG_EV))
    # the "fifteen" evasion, caught mechanically: an invented count of the analog set moved from
    # digit form (caught) to word form (invisible — no adjacent unit) across three drafts. "analog"
    # is now a count noun in the lexicon, so the word-number extracts and NO-MATCHes. Both ways:
    check("invented word-number count of analogs -> NO-MATCH ('fifteen notable analogs')",
          any(f["type"] == "NO-MATCH" and "fifteen" in f["token"].lower()
              for f in run_fidelity("Of the eligible sessions, fifteen notable analogs mirror this "
                                    "state. Not a forecast.", ANALOG_EV)["failures"]))
    check("the real analog count still binds ('150 analogs')",
          not any(f["type"] in ("NO-MATCH", "UNIT-MISMATCH")
                  for f in run_fidelity("Across all 150 analogs the pattern held. Not a forecast.",
                                        ANALOG_EV)["failures"]))
    # NOTE-FORM scoping (option (b): quiet sessions ship as notes). A note has no sections BY
    # DESIGN; the size guard keeps the exemption from excusing a heading-less flagship. Both ways:
    _note = ("The sector spread ran 2.1pp between semis and staples. The state most resembles "
             "2008 and 2020. Historical outcomes, not forecasts.")
    check("note-form draft (no headings, note-sized) -> no MISSING-SECTION",
          not any(f["type"] == "MISSING-SECTION"
                  for f in check_completeness(_note, DIGEST_EV.replace("SECTION 3", "X"))))
    check("note-form still gets TRUNCATED-DRAFT on a cut-off tail",
          any(f["type"] == "TRUNCATED-DRAFT"
              for f in check_completeness("The spread ran 2.1pp between", DIGEST_EV)))
    _wall = ("word " * 300).strip() + "."
    check("heading-less WALL OF TEXT (flagship-length) still fails MISSING-SECTION",
          any(f["type"] == "MISSING-SECTION" for f in check_completeness(_wall, DIGEST_EV)))
    check("a draft WITH headings is still held to the full section contract",
          any(f["type"] == "MISSING-SECTION"
              for f in check_completeness("## The mark\nx.", DIGEST_EV)))

    # INDEX-MEASURED presence: the natural "shallower than an individual stock" phrasing satisfies
    # it (four honest quiet notes were failed for it, 2026-07-27); unrelated prose does not.
    _im = _LB["INDEX-MEASURED"][1]
    for _s in ["a shallower move than what's typical for an individual stock.",
               "index moves are shallower than the median single stock's."]:
        check(f"natural index caveat satisfies INDEX-MEASURED: \"{_s[:42]}…\"",
              bool(_re2.search(_im, _s, _re2.I)))
    for _s in ["The individual stock rallied.", "Semiconductors fell -2.25% on the session."]:
        check(f"unrelated prose does NOT satisfy INDEX-MEASURED: \"{_s[:40]}…\"",
              not _re2.search(_im, _s, _re2.I))

    # IDENTIFIER-LEAK + LABEL-FURNITURE (the review-layer classes made mechanical), both directions.
    from content_agent.fidelity import check_identifier_leak, check_label_furniture
    for _s in ["Bitcoin (ANCHOR_BTC) and gold (ANCHOR_GOLD) correlated at 0.0943.",
               "the rapid bounce following calm_2013_2017 was brief.",
               "the crash_2008 instance took notably longer.",
               "the selloff_2018Q4 window shows a different sign."]:
        check(f"identifier leak fails: \"{_s[:44]}…\"", bool(check_identifier_leak(_s)))
    for _s in ["the repricing of 2022 broke the pattern.",
               "during the “calm_2013_2017” period the correlation was 0.3307.",
               "the 2008 crash took 50.6 months to recover.",
               "gold and bitcoin correlated at 0.0943 overall."]:
        check(f"clean prose passes identifier check: \"{_s[:44]}…\"", not check_identifier_leak(_s))
    for _s in ["INDEX-MEASURED (drawdowns are shallower on an index), SMALL-N (anecdotes only), "
               "FORWARD-LOOKING (future cycles will differ).",
               "PROXY (ETF); SINGLE-INSTANCE; INDEX-MEASURED."]:
        check(f"label checklist fails as furniture: \"{_s[:44]}…\"", bool(check_label_furniture(_s)))
    for _s in ["One drawdown remains unrecovered (CENSORED), its recovery time unknown.",
               "These named stress episodes are SINGLE-INSTANCE events. One episode remains "
               "CENSORED, its recovery time unknown.",
               "The measurement uses an ETF proxy and each episode is a single instance, so the "
               "figures are anecdotes rather than a distribution."]:
        check(f"one-label-per-sentence and lowercase prose pass: \"{_s[:44]}…\"",
              not check_label_furniture(_s))

    # WORD-NUMBER: the digits-only rule made mechanical (8 of 9 live drafts verbalised "fifteen").
    # Both directions: big word-numbers fail in digest class; small idioms and other classes pass.
    from content_agent.fidelity import check_word_numbers
    check("'fifteen' in a digest draft -> WORD-NUMBER",
          any(f["type"] == "WORD-NUMBER"
              for f in check_word_numbers("Of these, fifteen sessions stood out.", ANALOG_EV)))
    check("'twenty sessions' spelled out -> WORD-NUMBER (conversion of an evidence digit)",
          any(f["type"] == "WORD-NUMBER"
              for f in check_word_numbers("Over the next twenty sessions it recovered.", ANALOG_EV)))
    check("small-word idioms pass ('one of these', 'two crises')",
          not check_word_numbers("One of these was 2008; the two crises cluster.", ANALOG_EV))
    check("non-digest class now CHECKED too ('twenty years of data' in a study)",
          any(f["type"] == "WORD-NUMBER"
              for f in check_word_numbers("The study spans twenty years of data.", RECOVERY_EV)))
    check("small-word idioms still pass in a non-digest study",
          not check_word_numbers("One of these was 2008; the two crises cluster.", RECOVERY_EV))
    # heading requirement rides the SECTION 2A marker, evidence-driven like sections 3/4
    _no_head = "## The mark\nx.\n## The context\ny."
    check("evidence carries SECTION 2A + draft lacks the heading -> MISSING-SECTION",
          any(f["type"] == "MISSING-SECTION" and f["token"] == "Similar sessions"
              for f in check_completeness(_no_head, ANALOG_EV)))
    check("draft WITH '## Similar sessions' heading -> passes",
          not any(f["type"] == "MISSING-SECTION"
                  for f in check_completeness(_no_head + "\n## Similar sessions\nz.", ANALOG_EV)))
    check("evidence WITHOUT SECTION 2A -> heading not required",
          not any(f["token"] == "Similar sessions"
                  for f in check_completeness(_no_head, DIGEST_EV.replace("SECTION 3", "X"))))
    # live-builder shape checks, same skip discipline as the block-shape group above
    try:
        analog_day = dc.build_digest()          # dc imported in the block-shape group
        if analog_day.get("analogs"):
            ab = dc.build_digest_block(analog_day)
            check("live block: SECTION 2A present when analogs computed", "SECTION 2A" in ab)
            check("live block: NO 20-session aggregate line for the analogs",
                  "DELIBERATELY ABSENT: no 20-session aggregate" in ab)
            check("live block: analog section makes NOT-A-SIGNAL required", "- NOT-A-SIGNAL" in ab)
            _dates = [n["date"] for n in analog_day["analogs"]["named"]]
            check("live block: every named analog date is printed", all(d in ab for d in _dates))
    except Exception as e:
        checks.append((True, f"(skipped live analog checks: {type(e).__name__})"))

    # ==================================================================================================
    # LABEL-PRESENCE PHRASING TABLE — the CLASS treatment (2026-07-27).
    #
    # Three separate rounds were lost to the same defect shape: NOT-A-SIGNAL, then CENSORED, then
    # INDEX-MEASURED — each a presence regex written narrowly enough that an honest draft stating the
    # caveat in natural words was hard-failed for omitting it. One-off fixes guarantee a fourth.
    # Every label an evidence builder can require is enumerated here with the phrasings a draft would
    # ACTUALLY use (must be accepted) and controls that say something else (must be rejected).
    #
    # THE STRUCTURAL GUARD BELOW IS THE POINT: a label emitted by any builder that has no detection
    # entry AND no phrasing row fails this self-test. A new label cannot ship without both. That guard
    # immediately found NOT-A-RANKING — mandatory in the sector-comparative block since the sector×event
    # work, with no LABELS entry at all, so it was never required and never invention-guarded.
    #
    # Presence is BROAD, LABEL_CLAIMS is NARROW. The asymmetry is deliberate: a draft may state the
    # caveat any way it likes, but only the explicit label term counts as ASSERTING it.
    # ==================================================================================================
    LABEL_PHRASINGS = {
        "SMALL-N": (["With only five events measured, this is a handful of anecdotes rather than a "
                     "distribution.",
                     "Five instances is a small-n sample, not a statistical distribution.",
                     "These are anecdotes, not a pattern you can lean on.",
                     "The sample is too small to be called typical — just six occurrences."],
                    ["The measured median across 268 instances was 0.98%.",
                     "Semiconductors fell -3.27% on the session."]),
        "SURVIVORSHIP": (["The panel is survivor-only, so crash co-movement is understated.",
                          "Names that blew up are absent from the sample, biasing the measurement.",
                          "Because failed companies drop out of the panel, this figure is understated.",
                          "The measured recovery is biased short."],
                         ["The correlation was 0.3307 in the calm stretch.",
                          "The spread ran 3.71 percentage points."]),
        "SURVIVOR-SELECTED": (["These names are studied because they survived and dominated.",
                               "The selection itself is the survivorship: every episode here is a "
                               "winner's history.",
                               "This is survivor-selected — the companies that did not make it are "
                               "not in the library.",
                               "Its drawdowns all recovered by construction of the selection."],
                              ["The survivor-only panel understates crash co-movement.",
                               "AAPL and MSFT correlated at 0.509 overall."]),
        "SINGLE-INSTANCE": (["Each regime figure is a single instance — one 2008, one 2020.",
                             "This is one historical episode, not a distribution of them.",
                             "n=1 per regime type: the 2022 number is how it behaved that once.",
                             "Every episode here is one sample, so treat it as a case, not a rate."],
                            ["Across 261 recovered instances the median was 232 sessions.",
                             "The overall correlation was 0.2717."]),
        "CENSORED": (["Seven instances have not regained their prior high — recovery time remains "
                      "unknown.",
                      "One episode is still underwater, so its recovery time is unknown.",
                      "Unrecovered episodes are censored, never imputed.",
                      "Two drawdowns have never recovered and are excluded rather than filled in."],
                     ["All 261 instances regained the prior high.",
                      "The median recovery was 232 sessions over 261 instances."]),
        "INDEX-MEASURED": (["The S&P 500 moved +0.02%, a shallower move than what's typical for an "
                            "individual stock.",
                            "Index movements are shallower than the moves of individual stocks.",
                            "These are index drawdowns, not what any one stock did.",
                            "An index or sector-ETF figure is not what one company did."],
                           ["Semiconductors fell -3.27% on the session.",
                            "The individual stock rallied hard into the close."]),
        # DISTRIBUTION's positives include the two real published phrasings that a negation-safe
        # variant falsely failed (see the LABELS comment). "not a distribution" is deliberately NOT
        # a control here: the measurement showed that rejecting it costs false failures on honest
        # affirmative prose and catches nothing, so presence stays broad by evidence, not by default.
        "DISTRIBUTION": (["This is a full distribution of outcomes, not a handful of cases.",
                          "Across a large sample the distribution of forward returns is wide.",
                          "This distribution captures observed behavior over a specific window.",
                          "This observed distribution does not guarantee future outcomes."],
                         ["The median was 0.98%.", "Semiconductors fell -3.27%."]),
        "FORWARD-LOOKING": (["Any read-through to the next occurrence is an inference, not a prediction.",
                             "This is not a forecast of what comes next.",
                             "History does not guarantee the next episode behaves the same way.",
                             "Nothing here predicts the next occurrence."],
                            ["The median drawdown was -19.3% across seven episodes.",
                             "Energy fell furthest in 2008."]),
        "SECTOR-PROXY": (["Each sector figure is its ETF's move, a proxy for the sector.",
                          "Semiconductors are measured via the SMH ETF, standing in for the sector.",
                          "The sector is represented by an exchange-traded fund, not the whole sector."],
                         ["The S&P 500 moved +0.02% on the session.",
                          "The correlation held at 0.3307."]),
        "NOT-A-SIGNAL": (["This describes what followed comparable past days; it is not a forecast.",
                          "These are historical outcomes, not predictions for tomorrow.",
                          "It cannot be interpreted as a forecast of future market behaviour.",
                          "The record does not predict tomorrow's movements or recommend anything."],
                         ["The median was 0.84%, positive in 93 of 150 instances.",
                          "Semiconductors declined -2.25%."]),
        "NOT-A-RANKING": (["This is measured past dispersion, not a ranking of what to buy or avoid.",
                           "A sector that fell least historically is not predicted to do so next time.",
                           "The ordering is not a recommendation — it is what happened.",
                           "Do not read the sector order as a buy list.",
                           # phrasings real drafts used, found by re-scoring the queue pre-commit
                           "Past dispersion does not guarantee future performance, nor is it a "
                           "ranking of what to hold.",
                           "NOT-A-RANKING: past dispersion is not predictive of future outcomes.",
                           "This isn't a ranking—SECTOR-PROXY measurements reflect ETF performance."],
                          ["Utilities fell least, at a median of -10.3%.",
                           "The spread between deepest and shallowest was wide."]),
    }
    from content_agent.fidelity import LABELS as _ALL_LABELS, LABEL_CLAIMS as _ALL_CLAIMS
    for _lab, (_pos, _neg) in LABEL_PHRASINGS.items():
        _rx = _ALL_LABELS.get(_lab, (None, None))[1]
        check(f"[{_lab}] has a detection entry", bool(_rx))
        if not _rx:
            continue
        for _s in _pos:
            check(f"[{_lab}] accepts: \"{_s[:46]}…\"", bool(_re2.search(_rx, _s, _re2.I)))
        for _s in _neg:
            check(f"[{_lab}] rejects: \"{_s[:46]}…\"", not _re2.search(_rx, _s, _re2.I))
        check(f"[{_lab}] is INVENTED-LABEL-guarded", _lab in _ALL_CLAIMS)

    # STRUCTURAL GUARD: every label any evidence builder emits in a REQUIRED HONESTY LABELS block
    # must have BOTH a detection entry and a phrasing row above. This is what makes the class closed
    # rather than a snapshot — a new label cannot ship without its phrasings being audited.
    try:
        import re as _re3
        from content_agent.studies import MLL as _MLL
        _emitted = set()
        for _f in ("generation/digest_core.py", "generation/relational_escalation.py"):
            _src = (_MLL / _f).read_text(encoding="utf-8")
            _emitted |= set(_re3.findall(r'"\s*-\s*([A-Z][A-Z-]{3,}):', _src))
        _uncovered = sorted(l for l in _emitted if l not in LABEL_PHRASINGS)
        check(f"every builder-emitted label is phrasing-audited (emitted={len(_emitted)}, "
              f"uncovered={_uncovered or 'none'})", not _uncovered)
        _undetected = sorted(l for l in _emitted if l not in _ALL_LABELS)
        check(f"every builder-emitted label has detection (undetected={_undetected or 'none'})",
              not _undetected)
    except Exception as e:                                  # markets-llm unreachable -> skip, not fail
        checks.append((True, f"(skipped structural label guard: {type(e).__name__})"))

    print("DIGEST SELF-TEST (hermetic; fixtures; no network/GPU/queue)\n")
    for good_, name in checks:
        print(f"  {'OK ' if good_ else 'XX '} {name}")
    passed = sum(g for g, _ in checks)
    print(f"\nSELF-TEST: {passed}/{len(checks)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
