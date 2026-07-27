"""Measured-relationship (pair) self-test — hermetic: fixture evidence built by the REAL block
builder, fixture drafts, no network, no GPU, no queue writes. Locks the rules that make the pair
class honest (relational content rebuild, item 3):

  - the library enumerates pair: studies, ranked by regime spread, marquee pairs prioritised;
  - evidence_for("pair:...") renders via markets-llm's own build_evidence_block (bond proxy stated);
  - task routing: single-pair evidence -> PAIR_TASK; the comparative class must NOT be swallowed;
  - fidelity: correlations bind verbatim; an invented correlation NO-MATCHes; SURVIVORSHIP and
    SINGLE-INSTANCE are required and INVENTED-LABEL-guarded; a causal narration of a correlation
    fails (all-class causal rule).

  .venv/Scripts/python.exe scripts/pair_selftest.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from content_agent.fidelity import run_fidelity                              # noqa: E402
from content_agent.drafter import (DIGEST_TASK, FLAGSHIP_TASK,               # noqa: E402
                                   FLAGSHIP_TASK_COMPARATIVE, PAIR_TASK)
from content_agent.studies import evidence_for, list_library                 # noqa: E402


def main():
    ok, checks = True, []

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        checks.append((bool(cond), name))

    # --- library enumeration ------------------------------------------------------------------------
    lib = list_library()
    pair_ids = [s for s in lib if s.startswith("pair:")]
    check("library enumerates pair: studies", len(pair_ids) > 0)
    check("marquee pair (stock-bond) is ranked ahead of the recovery block",
          "pair:ANCHOR_RATE_10Y|ANCHOR_SPY" in lib
          and lib.index("pair:ANCHOR_RATE_10Y|ANCHOR_SPY") < lib.index("recovery:ANCHOR_SPY"))
    check("event studies still lead the library", lib[0].startswith("event:"))

    # --- evidence rendering (real artifact, real builder) -------------------------------------------
    ev = evidence_for("pair:ANCHOR_RATE_10Y|ANCHOR_SPY")
    check("evidence_for pair: returns a block", bool(ev and ev.get("evidence")))
    if not ev:
        _finish(checks, ok); return
    block = ev["evidence"]
    check("block is the single-pair class", "MEASURED RELATIONAL EVIDENCE" in block)
    check("bond-proxy sign-flip note present for the 10Y pair", "sign-FLIP" in block)
    check("per-regime rows carry SINGLE-INSTANCE framing", "SINGLE INSTANCE" in block
          or "SINGLE-INSTANCE" in block)
    check("provenance carries the regime spread used for ranking",
          isinstance(ev["provenance"].get("regime_spread"), float))

    # --- task routing -------------------------------------------------------------------------------
    def route(evidence):
        if "MEASURED DAILY DIGEST EVIDENCE" in evidence:
            return DIGEST_TASK
        if "SECTOR-BY-SECTOR" in evidence or "COMPARATIVE RELATIONAL" in evidence:
            return FLAGSHIP_TASK_COMPARATIVE
        if "MEASURED RELATIONAL EVIDENCE" in evidence:
            return PAIR_TASK
        return FLAGSHIP_TASK

    check("single-pair block routes to PAIR_TASK", route(block) is PAIR_TASK)
    check("comparative block is NOT swallowed by the pair route",
          route("MEASURED COMPARATIVE RELATIONAL EVIDENCE — ...") is FLAGSHIP_TASK_COMPARATIVE)
    check("digest block still routes to DIGEST_TASK",
          route("MEASURED DAILY DIGEST EVIDENCE — ...") is DIGEST_TASK)

    # --- fidelity on the pair class -----------------------------------------------------------------
    def fails(draft):
        return run_fidelity(draft, block)["failures"]

    goodish = ("Measured across regimes, each a single instance rather than a distribution, the "
               "correlation was 0.3307 in the calm stretch and -0.0977 in the repricing episode. "
               "The panel is survivor-only, so crash co-movement is understated.")
    check("verbatim correlations bind",
          not [f for f in fails(goodish) if f["type"] in ("NO-MATCH", "UNIT-MISMATCH")])
    check("an invented correlation -> NO-MATCH",
          any(f["type"] == "NO-MATCH" and "0.61" in f["token"]
              for f in fails("The correlation was 0.6123 in the calm stretch.")))
    r = run_fidelity("The correlation was 0.3307 in calm markets.", block)
    check("SURVIVORSHIP required and missing -> MISSING-LABEL",
          any(f["type"] == "MISSING-LABEL" and f["token"] == "SURVIVORSHIP" for f in r["failures"]))
    check("SINGLE-INSTANCE required and missing -> MISSING-LABEL",
          any(f["type"] == "MISSING-LABEL" and f["token"] == "SINGLE-INSTANCE" for f in r["failures"]))
    check("a causal narration of the correlation -> CAUSAL-CLAIM",
          any(f["type"] == "CAUSAL-CLAIM"
              for f in fails("Equities fell in 2022, driven by rising yields.")))
    check("plain co-movement prose does NOT fire the causal rule",
          not any(f["type"] == "CAUSAL-CLAIM"
                  for f in fails("Equities and yields moved together in 2022; the correlation "
                                 "was -0.0977, a single instance.")))
    # the two mandated-voice shapes that false-fired on the first live pair draft (2026-07-27),
    # locked both ways: the data-limit statement and the outside-factors disclaimer must pass;
    # a price-move assertion in the same vocabulary must still fail.
    check("'understated due to SURVIVORSHIP bias' is a data limit, not a cause",
          not any(f["type"] == "CAUSAL-CLAIM"
                  for f in fails("This number is understated due to survivorship bias; the names "
                                 "that disappeared are absent.")))
    check("'shifts driven by factors outside this analysis' is a disclaimer",
          not any(f["type"] == "CAUSAL-CLAIM"
                  for f in fails("The relationship is regime-contingent and prone to shifts driven "
                                 "by factors outside this analysis.")))
    check("...but 'stocks fell due to rising yields' still fails",
          any(f["type"] == "CAUSAL-CLAIM"
              for f in fails("Stocks fell in the repricing due to rising yields.")))
    check("...and 'the decline was driven by the yield move' still fails",
          any(f["type"] == "CAUSAL-CLAIM"
              for f in fails("The decline was driven by the yield move.")))

    _finish(checks, ok)


def _finish(checks, ok):
    print("PAIR SELF-TEST (hermetic; real artifact, fixture drafts; no network/GPU/queue)\n")
    for good_, name in checks:
        print(f"  {'OK ' if good_ else 'XX '} {name}")
    passed = sum(g for g, _ in checks)
    print(f"\nSELF-TEST: {passed}/{len(checks)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
