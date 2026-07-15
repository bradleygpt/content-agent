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
from content_agent.fidelity import run_fidelity  # noqa: E402

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
CLEAN_CORE = """Across the five measured midterms the median depth was -15.7% and the median recovery 3.6 months.
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
    check("D4 word-number that matches evidence (fourteen -> 14.0 months) still binds", rep["passed"])

    print("FIDELITY SELF-TEST (hermetic; real production texts embedded; no GPU/network)\n")
    for good, name in checks:
        print(f"  {'OK ' if good else 'XX '} {name}")
    passed = sum(g for g, _ in checks)
    print(f"\nSELF-TEST: {passed}/{len(checks)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
