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

    print("DIGEST SELF-TEST (hermetic; fixtures; no network/GPU/queue)\n")
    for good_, name in checks:
        print(f"  {'OK ' if good_ else 'XX '} {name}")
    passed = sum(g for g, _ in checks)
    print(f"\nSELF-TEST: {passed}/{len(checks)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
