"""Hypothesis-intake self-test (register #6 C-1) — hermetic: fixture tickets, no network, no GPU, no
queue writes. Locks the DETERMINISTIC layers — triage (testability mapping), the consistency check
(extraction treated as hostile), and the pair-verdict sign comparison. The 12B extraction itself is
validated by the live nightly cycle, not here.

  .venv/Scripts/python.exe scripts/hypothesis_selftest.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from content_agent.hypotheses import triage, consistency_check, test_ticket  # noqa: E402
from content_agent import hypotheses  # noqa: E402


def _ticket(claim, direction, assets, quote, conditions="", abstract=None):
    return {"paper_id": "test.0001", "paper_title": "t", "paper_date": "2026-07-18", "link": "",
            "claim": claim, "direction": direction, "assets": assets, "conditions": conditions,
            "quote": quote, "_abstract": abstract if abstract is not None else quote}


def main():
    ok, checks = True, []

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        checks.append((bool(cond), name))

    # --- triage ------------------------------------------------------------------------------------
    t = _ticket("bitcoin is negatively correlated with gold in stress", "inverse",
                ["bitcoin", "gold"], "we find bitcoin is inversely related to gold in stress periods")
    tri = triage(t)
    check("pair claim -> TESTABLE(pair)", tri["testable"] and tri["mode"] == "pair"
          and set(tri["anchors"]) == {"ANCHOR_BTC", "ANCHOR_GOLD"})

    t2 = _ticket("equities fall ahead of midterm elections", "negative", ["stocks"],
                 "equity markets decline ahead of midterm elections")
    tri2 = triage(t2)
    check("event claim -> TESTABLE(event midterm)", tri2["testable"] and tri2["mode"] == "event"
          and tri2["event"] == "midterm_election")

    t3 = _ticket("semiconductor drawdowns recover within a year", "none", ["semiconductors"],
                 "semiconductor drawdowns typically recover within twelve months")
    tri3 = triage(t3)
    check("recovery claim -> TESTABLE(recovery)", tri3["testable"] and tri3["mode"] == "recovery")

    t4 = _ticket("high-momentum stocks outperform in the cross-section", "outperform",
                 ["momentum stocks"], "the cross-section of returns shows momentum premia")
    tri4 = triage(t4)
    check("cross-sectional factor claim -> UNTESTABLE", not tri4["testable"]
          and "cross-sectional" in tri4["reason"])

    t5 = _ticket("copper predicts soybean futures", "predicts", ["copper", "soybeans"],
                 "copper returns predict soybean futures returns")
    tri5 = triage(t5)
    check("unmapped assets -> UNTESTABLE(outside anchor universe)",
          (not tri5["testable"]) and "outside the anchor universe" in tri5["reason"])
    # partial mapping ("em bonds" hits the bond proxy) without event/recovery structure is ALSO untestable,
    # with the one-anchor reason — the honest partial-map case
    t5b = _ticket("copper predicts emerging-market bonds", "predicts", ["copper", "em bonds"],
                  "copper returns predict emerging market bond returns")
    tri5b = triage(t5b)
    check("partial map, no structure -> UNTESTABLE(one anchor)",
          (not tri5b["testable"]) and "one mapped anchor" in tri5b["reason"])

    check("no-claim ticket -> UNTESTABLE", not triage(_ticket("", "none", [], ""))["testable"])

    # --- consistency check (hostile extraction) ------------------------------------------------------
    c1 = consistency_check(t, tri["mapped"])
    check("clean ticket verifies (assets + direction in quote)", c1["verified"])

    bad_asset = _ticket("bitcoin hedges gold", "inverse", ["bitcoin", "gold"],
                        "we study volatility spillovers in energy markets")   # quote lacks the assets
    trib = triage(bad_asset)
    cb = consistency_check(bad_asset, trib.get("mapped", []))
    check("asset absent from quote -> UNVERIFIED", not cb["verified"])

    bad_dir = _ticket("bitcoin rises with gold", "positive", ["bitcoin", "gold"],
                      "bitcoin and gold and stress hedging")                   # no direction words
    trid = triage(bad_dir)
    cd = consistency_check(bad_dir, trid.get("mapped", []))
    check("direction unsupported by quote -> UNVERIFIED", not cd["verified"])

    fab = _ticket("bitcoin inversely tracks gold", "inverse", ["bitcoin", "gold"],
                  "bitcoin is inversely related to gold",
                  abstract="this paper studies option pricing under jumps")    # quote not in abstract
    trif = triage(fab)
    cf = consistency_check(fab, trif.get("mapped", []))
    check("quote not verbatim from abstract -> UNVERIFIED (fabricated quote)", not cf["verified"])

    # --- pair verdict sign comparison (fixture artifact; loader monkeypatched) ----------------------
    class _FakeRE:
        @staticmethod
        def load_evidence(pair):
            return {"overall_corr": -0.31,
                    "episodes": {"covid_2020": {"corr": -0.5}, "calm": {"corr": -0.1}}}

        @staticmethod
        def load_event_evidence(k):
            return None

        @staticmethod
        def load_recovery_evidence(a):
            return None
    sys.modules["relational_escalation"] = _FakeRE()  # type: ignore

    r = test_ticket(_ticket("x", "inverse", [], "q"), {"mode": "pair",
                                                       "anchors": ["ANCHOR_BTC", "ANCHOR_GOLD"]})
    check("inverse claim vs measured -0.31 -> supported", r["verdict"] == "supported")
    r2 = test_ticket(_ticket("x", "positive", [], "q"), {"mode": "pair",
                                                         "anchors": ["ANCHOR_BTC", "ANCHOR_GOLD"]})
    check("positive claim vs measured -0.31 -> contradicted", r2["verdict"] == "contradicted")
    r3 = test_ticket(_ticket("x", "inverse", [], "q"), {"mode": "event", "event": "nope"})
    check("missing artifact -> NEEDS-EXTENSION", r3["verdict"] == "NEEDS-EXTENSION")
    del sys.modules["relational_escalation"]

    print("HYPOTHESIS-INTAKE SELF-TEST (hermetic; fixtures; no network/GPU/queue)\n")
    for good, name in checks:
        print(f"  {'OK ' if good else 'XX '} {name}")
    passed = sum(g for g, _ in checks)
    print(f"\nSELF-TEST: {passed}/{len(checks)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
