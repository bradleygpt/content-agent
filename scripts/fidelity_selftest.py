"""Fidelity checker self-test — deterministic, hermetic (embedded fixtures), no GPU, no network. Joins the
standing test suite next to chart_selftest.py and c0_validate --selftest.

  .venv/Scripts/python.exe scripts/fidelity_selftest.py

Covers the 2026-07-15 checker-tuning pass against REAL production texts (embedded verbatim):
  A. INVENTED-LABEL — the actual SURVIVORSHIP-misuse paragraph from queue draft 20260713T205947-3c2dfb
     (claimed survivorship filtering on a study where all five events were included) must HARD-FAIL;
     a clean control on the same evidence must pass.
  B. Trigger metadata as evidence — the actual "approximately 16 weeks remaining" sentence from draft
     20260714T130707-bacf69 must NO-MATCH against the bare study block and BIND once the TRIGGER CONTEXT
     section (as run_daily now appends) is present.
  C. Directional scope — the actual number-free narrative sentence from piece #2 (20260714T181942-52b903)
     with number-free neighbors must NOT be flagged; the "upward drift" embellishment next to an
     engine-attributed numeric claim must STILL be flagged; a numeric directional sentence still flags.
  D. Core regressions — months-vs-weeks UNIT-MISMATCH, missing-label enforcement, word-number binding.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from content_agent.fidelity import (run_fidelity, _N_RX, _AVERAGE_RX,  # noqa: E402
                                    _is_evidence_text)

# The real midterm evidence block (trimmed; same labels + figures as production: SMALL-N + FORWARD-LOOKING
# required, NO SURVIVORSHIP).
MIDTERM_EV = """MEASURED EVENT-CONDITIONED EVIDENCE — from the standalone relational engine (measured from daily prices; NOT in the corpus).
Event type: US midterm elections on the US stock market (SPY).
SMALL-N: 5 events only — these are 5 anecdotes with a pattern, NOT a statistical distribution.
Per-event:
    2006-11-07: depth -7.6%, recovered in 3.0mo.
    2010-11-02: depth -15.7%, recovered in 4.1mo.
    2014-11-04: depth -7.3%, recovered in 0.5mo.
    2018-11-06: depth -19.3%, recovered in 3.6mo.
    2022-11-08: drawdown began 10.2mo before the event, depth -24.5%, recovered in 14.0mo.
Across the 5: depth median -15.7, range -24.5..-7.3%; recovery median 3.6, range 0.5..14.0 months; 0 never recovered.
REQUIRED HONESTY LABELS (carry into the answer):
  - SMALL-N: 5 events is a pattern across a handful of anecdotes, not a distribution.
  - FORWARD-LOOKING: any read-through to a future occurrence is an inference, not a prediction."""

# A compliant core draft (verbatim digits, both required labels) used as the base for several cases.
# 2026-07-31: the first sentence gained its RANGES. check_median_discipline was digest-gated until
# now, so this "clean control" had never actually been subject to it — it is not that the sentence
# passed the rule, it is that the rule never ran on a study-class fixture. Ungating it made the
# omission visible. The fixture is updated to meet the standard rather than the standard relaxed to
# meet the fixture: a median depth and a median recovery each carry N and range in their own sentence,
# which is exactly what the class now demands of a real draft.
CLEAN_CORE = """Across the five measured midterms the median depth was -15.7%, ranging from -7.3% to
-24.5%; across those same five midterms the median recovery was 3.6 months, with a range of 0.5 to
14.0 months.
These are 5 anecdotes with a pattern, a handful of cases, not a distribution. In 2022 the drawdown began
10.2 months before the event and took 14.0 months to recover; in 2014 recovery took 0.5 months.
History here is an inference from these cases — it cannot predict the next occurrence."""

# VERBATIM from queue draft 20260713T205947-3c2dfb (the SURVIVORSHIP misuse — evidence includes all five
# events; nothing was selected on recovery).
SURV_MISUSE_PARA = ("Consider also the *SURVIVORSHIP* caveat. This relational engine has measured five "
                    "elections, but there may be previous instances that did not exhibit this pattern—they "
                    "simply weren't captured by the analysis's constraints or definition of a drawdown. "
                    "Therefore, the impression of a recurring phenomenon might be influenced by selection "
                    "bias.")

# VERBATIM from queue draft 20260714T130707-bacf69 (trigger-sourced framing number).
TRIG_SENT = "With approximately 16 weeks remaining until the next midterm election, the measured record is the context."
TRIGGER_CTX = ("\n\nTRIGGER CONTEXT (provenance metadata; legitimate numeric evidence):\n"
               "- midterm election on 2026-11-03 is 16.0 weeks away — countdown piece\n"
               "- 16.0 weeks until the event")

# VERBATIM from queue draft 20260714T181942-52b903 (number-free narrative false-positive) + its real
# number-free neighbors.
FP_NARRATIVE = ("This level of dispersion complicates, if not undermines, the notion of a predictable "
                "sector rotation playbook. The idea that certain sectors consistently outperform or "
                "underperform around midterm elections simply isn't supported by this measured evidence. "
                "There is no consistent order to these outcomes.")

# The "upward drift" embellishment class (port-fixture Case-2 shape): number-free directional sentence
# RIDING NEXT TO an engine-attributed numeric claim — must still be flagged.
FOMC_EV = """MEASURED EVENT-CONDITIONED EVIDENCE — from the relational engine (measured since 2004; NOT corpus).
LARGE-N: 166 events — an empirical distribution.
Across the 166: depth median -4.2%, range -35.0..-0.7%.
FORWARD-LOOKING: an inference from these cases, not a prediction."""
DRIFT_EMBELLISH = ("Across the 166 meetings measured since 2004 the median drawdown was -4.2%, a "
                   "distribution, not a prediction. The data shows the market tends to drift higher and "
                   "rally in the weeks after the meeting. That inference cannot predict the next meeting.")


def main():
    ok, checks = True, []

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        checks.append((bool(cond), name))

    def types(rep):
        return [f["type"] for f in rep["failures"]]

    def tokens_of(rep, ftype):
        return {f["token"] for f in rep["failures"] if f["type"] == ftype}

    # --- A. invented label -------------------------------------------------------------------------
    rep = run_fidelity(CLEAN_CORE + "\n\n" + SURV_MISUSE_PARA, MIDTERM_EV)
    check("A1 misuse draft hard-fails", not rep["passed"])
    check("A2 failure class is INVENTED-LABEL:SURVIVORSHIP",
          tokens_of(rep, "INVENTED-LABEL") == {"SURVIVORSHIP"})
    check("A3 label row marked invented", rep["labels"]["SURVIVORSHIP"].get("invented") is True)
    rep = run_fidelity(CLEAN_CORE, MIDTERM_EV)
    check("A4 clean control passes", rep["passed"])
    check("A5 clean control has no INVENTED-LABEL", "INVENTED-LABEL" not in types(rep))
    # a draft honestly saying "not a distribution" on SMALL-N must NOT trip DISTRIBUTION
    check("A6 'not a distribution' is not an invented DISTRIBUTION",
          "DISTRIBUTION" not in tokens_of(run_fidelity(CLEAN_CORE, MIDTERM_EV), "INVENTED-LABEL"))
    # required-label direction unchanged: evidence WITH SURVIVORSHIP still demands it
    ev_s = MIDTERM_EV + "\n  - SURVIVORSHIP: only surviving constituents are measured."
    check("A7 required SURVIVORSHIP still enforced (missing -> fail)",
          "SURVIVORSHIP" in tokens_of(run_fidelity(CLEAN_CORE, ev_s), "MISSING-LABEL"))
    check("A8 required SURVIVORSHIP satisfied when stated",
          run_fidelity(CLEAN_CORE + "\n\n" + SURV_MISUSE_PARA, ev_s)["passed"])

    # --- B. trigger metadata as evidence -----------------------------------------------------------
    rep = run_fidelity(CLEAN_CORE + "\n\n" + TRIG_SENT, MIDTERM_EV)
    check("B1 trigger-sourced '16 weeks' NO-MATCHes bare study block",
          any(f["token"].startswith("16") for f in rep["failures"] if f["type"] == "NO-MATCH"))
    rep = run_fidelity(CLEAN_CORE + "\n\n" + TRIG_SENT, MIDTERM_EV + TRIGGER_CTX)
    check("B2 binds once TRIGGER CONTEXT rides the evidence", rep["passed"])
    rep = run_fidelity(CLEAN_CORE + "\n\nThe 2026 cycle (election 2026-11-03) is the next test.",
                       MIDTERM_EV + TRIGGER_CTX)
    check("B3 trigger date + year bind too", rep["passed"])

    # --- C. directional scope ----------------------------------------------------------------------
    rep = run_fidelity(FP_NARRATIVE, MIDTERM_EV)
    check("C1 number-free narrative with number-free neighbors NOT flagged",
          rep["directional"] == [])
    rep = run_fidelity(DRIFT_EMBELLISH, FOMC_EV)
    check("C2 'drift higher' embellishment next to attributed stat STILL flagged",
          any("drift higher" in d["sentence"] for d in rep["directional"]))
    rep = run_fidelity("The engine measured that the market tends to fall -15.7% into midterms.", MIDTERM_EV)
    check("C3 numeric directional sentence still flagged, numbers bound",
          len(rep["directional"]) == 1 and rep["directional"][0]["numbers_bound"])

    # --- D. core regressions (strictness unchanged) ------------------------------------------------
    rep = run_fidelity("Recovery took a median of 3.6 weeks.", MIDTERM_EV)
    check("D1 months-vs-weeks is still UNIT-MISMATCH", "UNIT-MISMATCH" in types(rep))
    rep = run_fidelity("Median recovery was 3.6 months.", MIDTERM_EV)  # missing both labels
    check("D2 missing labels still fail",
          {"SMALL-N", "FORWARD-LOOKING"} <= tokens_of(rep, "MISSING-LABEL"))
    rep = run_fidelity(CLEAN_CORE + "\n\nRecovery took ten months in one case.", MIDTERM_EV)
    check("D3 word-number rounding ('ten months' for 10.2) still NO-MATCH — checker stays strict",
          any(f["token"].startswith("ten") for f in rep["failures"] if f["type"] == "NO-MATCH"))
    rep = run_fidelity(CLEAN_CORE.replace("In 2022 the drawdown began\n10.2 months",
                                          "In 2022 the drawdown began\nfourteen months"), MIDTERM_EV)
    # D4 tests the BINDER, not the whole report. Its old assertion was rep["passed"], which stopped
    # being the right question on 2026-07-31: check_word_numbers is no longer digest-gated, so
    # spelling out a number eleven-and-above now fails in EVERY class and this draft correctly does
    # not pass. What must still hold is that "fourteen" BINDS to the evidence's 14.0 — otherwise an
    # invented word-number would go unextracted and sail through, which is the bug D4 was written for.
    check("D4 word-number that matches evidence (fourteen -> 14.0 months) still binds",
          not any(f["type"] == "NO-MATCH" and "fourteen" in f["token"] for f in rep["failures"]))
    check("D4b ... and the spelled-out form is now itself a WORD-NUMBER failure (ungated)",
          any(f["type"] == "WORD-NUMBER" and "fourteen" in f["token"].lower()
              for f in rep["failures"]))

    # --- THE DISCLAIMER SHIELD (2026-07-31) ---------------------------------------------------------
    # Every string below is VERBATIM from the real queue, not invented for the test. Two of the three
    # preambles were already PUBLISHED when the bypass was found, which is why they are pinned here:
    # the rule matched the causal vocabulary in all three and was talked out of firing by disclaimer
    # words sitting earlier in the same sentence.
    from content_agent.fidelity import _causal_is_asserted as _asserted
    PREAMBLES = [   # a denial that precedes named causes is not a denial — these MUST be caught
        ("KOSPI: denial, colon, four named causes",
         "The observed dispersion is likely attributable to factors beyond the scope of this "
         "measurement: idiosyncratic company events impacting KOSPI-listed firms, changes in investor "
         "sentiment towards Korean equities, global economic shocks affecting regional markets, and "
         "shifts in macroeconomic policy influencing capital flows."),
        ("PUBLISHED election-sector: denial, semicolon, three named causes",
         "The measured outcomes are driven by factors beyond simple risk-on/risk-off sentiment; "
         "company-specific events, broader macroeconomic shifts not directly tied to the election "
         "outcome, and unexpected geopolitical developments all play a role in shaping sector "
         "performance."),
        ("PUBLISHED FOMC: 'unique circumstances', dash, three named causes",
         "These extremes are driven by unique circumstances surrounding each FOMC meeting - shifts in "
         "monetary policy, unexpected economic data releases, or broader market sentiment."),
    ]
    DISCLAIMERS = [  # genuine disclaimers name NO causes — these MUST stay exempt
        ("myriad factors, no enumeration",
         "Primarily, it reminds us that markets are complex systems driven by myriad factors."),
        ("numerous factors, no enumeration",
         "While this measurement provides a historical snapshot, it is crucial to remember that "
         "markets are complex adaptive systems driven by numerous factors."),
        ("factors not captured, no enumeration",
         "The pattern observed here might be entirely coincidental or driven by factors not captured "
         "within the relational engine's event-conditioned measurement."),
        ("factors outside this analysis, no enumeration",
         "The relationship is regime-contingent and prone to shifts driven by factors outside this "
         "analysis."),
        ("a list of LIMITATIONS is not a list of causes",
         "It highlights recurring patterns but also underscores their limitations due to the SMALL-N "
         "size, *SURVIVORSHIP* bias, and inherent *REGIME DEPENDENCE*."),
    ]
    for name, s in PREAMBLES:
        check(f"disclaimer-shield: CAUGHT - {name}", _asserted(s))
    for name, s in DISCLAIMERS:
        check(f"disclaimer-shield: still exempt - {name}", not _asserted(s))

    # --- SPLIT SCOPING: piece for flagships, sentence for notes (2026-07-31) ---------------------
    from content_agent.fidelity import check_median_discipline as _cmd
    _far = ("The median depth was -15.7%.\n\nSeparately, across the five measured midterms the "
            "spread ran from -7.3% to -24.5%.")
    check("flagship: N and range elsewhere in the piece SATISFY the median",
          not _cmd(_far, "RECOVERY ev", kind="flagship"))
    check("note: the same text still FAILS — a note's sentence is very nearly the piece",
          any(f["type"] == "MEDIAN-WITHOUT-N" for f in _cmd(_far, "RECOVERY ev", kind="note")))
    check("unknown kind defaults to the STRICT sentence reading",
          any(f["type"] == "MEDIAN-WITHOUT-N" for f in _cmd(_far, "RECOVERY ev")))
    check("flagship with the statistic nowhere in the piece still fails",
          any(f["type"] == "MEDIAN-WITHOUT-N"
              for f in _cmd("The median depth was -15.7%.", "RECOVERY ev", kind="flagship")))

    # --- BARE-AVERAGE now distinguishes REPORTING an average from ARGUING AGAINST one ------------
    for _lbl, _s, _want in [
        ("published: 'isn't captured by simple averages' stays silent",
         "reflecting an underlying tension that isn't captured by simple averages.", False),
        ("published: 'does not tell the full story; it's an average' stays silent",
         "This number alone does not tell the full story; it's an average across conditions.", False),
        ("a REPORTED average still fires", "The average drawdown was -12.3%.", True),
        ("preamble guard: denial then a reported average still fires",
         "Averages do not capture this, but the average was -12.3% over the window.", True),
    ]:
        _got = any(f["type"] == "BARE-AVERAGE" for f in _cmd(_s, "RECOVERY ev"))
        check(f"BARE-AVERAGE: {_lbl}", _got == _want)

    # --- _N_RX RECALL TABLE. Enumerated from every "<number> <noun>" in every queued draft, ranked
    # by use, rather than patched one incident at a time. The distinction the list encodes is COUNT
    # NOUN vs UNIT NOUN: a unit answers how long or how far, never how many observations.
    for _noun, _is_count in [("events", True), ("instances", True), ("episodes", True),
                             ("drawdowns", True), ("cases", True), ("samples", True),
                             ("midterms", True), ("elections", True), ("meetings", True),
                             ("cycles", True), ("observations", True), ("times", True),
                             ("crises", True), ("occurrences", True),
                             # units — must NOT satisfy N, or "3.6 months" reads as N=3.6
                             ("months", False), ("weeks", False), ("years", False),
                             ("points", False), ("percent", False)]:
        _got = bool(_N_RX.search(f"across the five {_noun}")) or bool(_N_RX.search(f"5 {_noun}"))
        check(f"_N_RX {'counts' if _is_count else 'ignores'} '{_noun}'", _got == _is_count)

    # --- _is_evidence_text on STUDY-class blocks (never exercised on that shape before) ----------
    from content_agent.studies import evidence_for as _evf
    for _sid in ("recovery:ANCHOR_KOSPI", "pair:ANCHOR_BTC|ANCHOR_GOLD", "event:midterm_election"):
        _ev = _evf(_sid)["evidence"]
        _sneak = _ev.splitlines()[1].strip()[:60] + " and the average was 0.2% across the set."
        _m = list(_AVERAGE_RX.finditer(_sneak))[-1]
        check(f"_is_evidence_text does NOT shield a violation wrapped in quoted evidence ({_sid})",
              not _is_evidence_text(_sneak, _m, _ev))

    print("FIDELITY SELF-TEST (hermetic; real production texts embedded; no GPU/network)\n")
    for good, name in checks:
        print(f"  {'OK ' if good else 'XX '} {name}")
    passed = sum(g for g, _ in checks)
    print(f"\nSELF-TEST: {passed}/{len(checks)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
