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

    # VALUES READ FROM THE RENDERED BLOCK, not frozen at authoring time (2026-08-01). The pinned
    # 0.3307/-0.0977 went stale at the fourth decimal when the RATE_10Y substrate repointed to FRED
    # (7 revised historical prints inside the fixed episode windows) — a fixture that hard-codes
    # artifact numbers re-breaks on every legitimate refresh, and the test's claim is "VERBATIM
    # values BIND", which is precisely a claim about values copied from the evidence.
    import re as _re
    _corrs = _re.findall(r"corr (-?\d\.\d+)", block)
    _calm, _repr = _corrs[1], _corrs[5]
    goodish = ("Measured across regimes, each a single instance rather than a distribution, the "
               f"correlation was {_calm} in the calm stretch and {_repr} in the repricing episode. "
               "The panel is survivor-only, so crash co-movement is understated.")
    check("verbatim correlations bind",
          not [f for f in fails(goodish) if f["type"] in ("NO-MATCH", "UNIT-MISMATCH")])
    check("an invented correlation -> NO-MATCH",
          any(f["type"] == "NO-MATCH" and "0.61" in f["token"]
              for f in fails("The correlation was 0.6123 in the calm stretch.")))
    r = run_fidelity(f"The correlation was {_calm} in calm markets.", block)
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
                                 f"was {_repr}, a single instance.")))
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

    # --- SIGN-FLIP INVERSION: the decidable direction-of-claim error, locked both ways --------------
    from content_agent.fidelity import check_sign_flip_inversion as _sfi
    wrong = ("Remember that bond prices move inversely to yields; therefore, this negative "
             "correlation indicates that stock and bond prices were moving in opposite directions.")
    check("negative corr narrated as prices 'opposite directions' -> SIGN-FLIP-INVERSION",
          any(f["type"] == "SIGN-FLIP-INVERSION" for f in _sfi(wrong, block)))
    right = ("Remember that bond prices move inversely to yields; therefore, this negative "
             "correlation means stock and bond prices were moving in the same direction.")
    check("the CORRECT flip narration passes", not _sfi(right, block))
    check("positive corr + prices 'same direction' -> SIGN-FLIP-INVERSION",
          any(f["type"] == "SIGN-FLIP-INVERSION"
              for f in _sfi(f"The positive correlation of {_calm} means stock and bond prices moved "
                            "in the same direction.", block)))
    check("positive corr + prices 'opposite directions' passes (correct flip)",
          not _sfi(f"The positive correlation of {_calm} means stock and bond prices moved in "
                   "opposite directions.", block))
    check("yield-basis direction prose without 'prices' is not judged",
          not _sfi("Stocks and yields moved in opposite directions; the correlation was negative.",
                   block))
    check("the flip-rule statement alone never fires",
          not _sfi("Bond prices move inversely to yields.", block))
    check("no sign-FLIP note in evidence -> check inert",
          not _sfi(wrong, "MEASURED RELATIONAL EVIDENCE with no proxy note"))

    # --- SURVIVOR-SELECTED (single-name pairs slice), both directions ------------------------------
    # A bare-ticker side makes the evidence carry the label (the renderer emits it structurally);
    # the anchor-anchor pair must NOT carry it; presence needs the selection concept, and honestly
    # carrying it must not read as inventing SURVIVORSHIP.
    ev_sn = evidence_for("pair:AAPL|MSFT")
    if ev_sn:
        blk = ev_sn["evidence"]
        check("single-name pair evidence carries SURVIVOR-SELECTED", "SURVIVOR-SELECTED" in blk)
        check("anchor-anchor pair evidence does NOT", "SURVIVOR-SELECTED" not in block)
        _r1 = run_fidelity("AAPL and MSFT are studied because they survived and dominated; the "
                           "correlation was 0.5043. Each regime is one historical instance; the "
                           "survivor-only panel understates crashes.", blk)
        check("selection concept satisfies SURVIVOR-SELECTED",
              not any(f["token"] == "SURVIVOR-SELECTED" and f["type"] == "MISSING-LABEL"
                      for f in _r1["failures"]))
        _r2 = run_fidelity("The correlation was 0.5043; the survivor-only panel understates "
                           "crashes. Each regime is one historical instance.", blk)
        check("bare 'survivor' does NOT satisfy SURVIVOR-SELECTED (selection concept required)",
              any(f["token"] == "SURVIVOR-SELECTED" and f["type"] == "MISSING-LABEL"
                  for f in _r2["failures"]))
        _r3 = run_fidelity("These names are survivor-selected winners; corr 0.5043; single "
                           "instances; survivor-only panel understates crashes.", blk)
        check("'survivor-selected' does not fire INVENTED SURVIVORSHIP (lookahead)",
              not any(f["type"] == "INVENTED-LABEL" for f in _r3["failures"]))
        check("asserting SURVIVOR-SELECTED where evidence lacks it -> INVENTED-LABEL",
              any(f["type"] == "INVENTED-LABEL" and f["token"] == "SURVIVOR-SELECTED"
                  for f in run_fidelity(f"This anchor set is survivor-selected. Corr {_calm}; single "
                                        "instances; survivor-only panel.", block)["failures"]))
    else:
        checks.append((True, "(skipped SURVIVOR-SELECTED checks: AAPL|MSFT not in artifact yet)"))

    # --- TENSION RULE (2026-07-28), both directions ------------------------------------------------
    from content_agent.studies import is_draftable
    import content_agent.studies as _st
    _resc = _st.resc
    _pairs = _st._pair_studies()
    if _pairs:
        _t1 = _resc.pair_tension(_pairs["ANCHOR_RATE_10Y|ANCHOR_SPY"])
        check("stock-bond pair tension is the SIGN FLIP", _t1 and _t1["kind"] == "sign_flip")
        _t2 = _resc.pair_tension(_pairs["ANCHOR_BTC|ANCHOR_GOLD"])
        check("BTC-gold tension is ZERO-ANCHOR (near-zero overall, same-signed episodes)",
              _t2 and _t2["kind"] == "zero_anchor")
        check("a uniform pair (XLC|META, spread 0.069) has NO tension -> NOT-DRAFTABLE",
              _resc.pair_tension(_pairs["ANCHOR_XLC|META"]) is None)
        check("tension line leads the draftable pair's evidence block",
              "THE TENSION" in evidence_for("pair:ANCHOR_RATE_10Y|ANCHOR_SPY")["evidence"])
        check("no tension line in a NOT-DRAFTABLE pair's block (explicit-request path)",
              "THE TENSION" not in evidence_for("pair:ANCHOR_XLC|META")["evidence"])
        _lib = list_library()
        check("NOT-DRAFTABLE pairs never reach the picker", "pair:ANCHOR_XLC|META" not in _lib)
        check("boring recovery anchors (DXY, XLP) never reach the picker",
              "recovery:ANCHOR_DXY" not in _lib and "recovery:ANCHOR_XLP" not in _lib)
        check("XLE recovery survives (50.6mo outlier vs 2.8mo median + censored)",
              is_draftable("recovery:ANCHOR_XLE") and "recovery:ANCHOR_XLE" in _lib)
        check("events survive via the authored folklore foil",
              all(is_draftable(f"event:{k}") for k in ("midterm_election", "pres_election",
                                                        "fomc_meeting")))
        _evb = evidence_for("event:midterm_election")["evidence"]
        check("event block leads with folklore-as-foil, labelled",
              "THE TENSION" in _evb and "folklore" in _evb.lower())

        # --- INTERNATIONAL ANCHORS (2026-07-30) -----------------------------------------------
        # Two conventions were settled by measurement and cost real work to settle; a silent drop
        # would leave a number that reads like the others but means something else. Both are
        # asserted STRUCTURALLY (present in the rendered block), never left to the drafter.
        from content_agent.fidelity import _ANCHOR_LEAK_RX as _akrx0
        for _a, _mkt in (("KOSPI", "Korea"), ("NIKKEI", "Japan"), ("TWII", "Taiwan")):
            _sid = f"recovery:ANCHOR_{_a}"
            _ib = evidence_for(_sid)["evidence"]
            check(f"{_a} recovery block states the LOCAL-CURRENCY basis",
                  "LOCAL-CURRENCY" in _ib)
            # the convention is carried in PROSE, not as "US[D-1]": it is a directive line, and the
            # df6ab61 law keeps directives digit-free so a mandated figure cannot be recited as data.
            _al = next((l for l in _ib.splitlines() if "CROSS-MARKET ALIGNMENT" in l), "")
            check(f"{_a} recovery block states the cross-market alignment convention",
                  bool(_al) and "PRIOR" in _al)
            # the directive must SUPPRESS the comparison, not invite it: the first live KOSPI draft
            # failed fidelity because an unconditional statement of the convention prompted a
            # trading-hours sentence the single-market piece never needed.
            check(f"{_a} alignment directive suppresses an uninvited cross-market aside",
                  bool(_al) and "none should be invented" in _al)
            check(f"{_a} alignment directive stays digit-free (df6ab61 law)",
                  bool(_al) and not any(c.isdigit() for c in _al))
            check(f"{_a} block never leaks the raw anchor id into prose",
                  not list(_akrx0.finditer(_ib)))
        check("international anchors are draftable and reach the picker",
              all(is_draftable(f"recovery:ANCHOR_{a}") and f"recovery:ANCHOR_{a}" in _lib
                  for a in ("KOSPI", "NIKKEI", "TWII")))
        # the live KOSPI drawdown is unresolved; CENSORED must be structural, not drafter-authored
        check("KOSPI block carries CENSORED for the still-underwater drawdown",
              "CENSORED" in evidence_for("recovery:ANCHOR_KOSPI")["evidence"])

        # --- PROSE DEFECTS FOUND IN THE PUBLISHED KOSPI TEXT (2026-07-31) ----------------------
        # Both were EVIDENCE-SHAPE, not drafting: the block handed the model machine artefacts and
        # the model faithfully copied them. "1 episode(s)" reached a sentence with its plural marker
        # intact, and the readable episode names still dragged their quoted keys along, so the
        # display-name work stopped the BARE key leaking and not the key itself.
        import re as _re
        for _sid in ("recovery:ANCHOR_KOSPI", "recovery:ANCHOR_XLE", "pair:ANCHOR_BTC|ANCHOR_GOLD",
                     "event:midterm_election"):
            _b = evidence_for(_sid)["evidence"]
            _pl = _re.findall(r"\w+\(s\)", _b)
            check(f"no '(s)' plural marker in {_sid}" + (f" — FOUND {_pl}" if _pl else ""), not _pl)
            _qk = _re.findall(r"\(\"[a-z0-9_]+\"\)", _b)
            check(f"no quoted episode key reaches prose in {_sid}"
                  + (f" — FOUND {_qk}" if _qk else ""), not _qk)
        check("episode names are still READABLE after dropping the key",
              "the 2008 crash" in evidence_for("recovery:ANCHOR_KOSPI")["evidence"])
        check("singular count agrees ('1 episode', never '1 episodes')",
              "1 episode " in evidence_for("recovery:ANCHOR_KOSPI")["evidence"])

    # --- EPISODE-KEY EMISSION AUDIT (2026-07-29): every rendered evidence block, all builders ------
    # The A/B measured every model copying the evidence's bare `covid_2020` into prose (pair shape
    # 0/6 across five arms). The fix is uniform quoting via _epq at EVERY emission site; this scan
    # renders one block per builder and fails on any bare key, so a future emission site cannot
    # quietly regress into a new pair-column. The checker's own leak regex is the scanner.
    from content_agent.fidelity import _ANCHOR_LEAK_RX as _akrx
    from content_agent.fidelity import _EPISODE_KEY_RX as _ekrx
    _blocks = {
        "pair (sign-flip tension + fingerprint rows)":
            evidence_for("pair:ANCHOR_RATE_10Y|ANCHOR_SPY")["evidence"],
        "pair (zero-anchor tension)": evidence_for("pair:ANCHOR_BTC|ANCHOR_GOLD")["evidence"],
        "recovery (outlier tension + notable rows)": evidence_for("recovery:ANCHOR_XLE")["evidence"],
        "event (folklore lead)": evidence_for("event:midterm_election")["evidence"],
        "recovery (international / censored)": evidence_for("recovery:ANCHOR_KOSPI")["evidence"],
    }
    for _name, _blk in _blocks.items():
        _bare = sorted({m.group(0) for m in _ekrx.finditer(_blk)})
        check(f"no bare episode keys in {_name} block"
              + (f" — FOUND {_bare}" if _bare else ""), not _bare)
        # ANCHOR_* audit (round-2 rerun finding): the pair HEADER leaked raw anchor ids into every
        # model's prose because it was the only name on offer. Prose-facing lines carry readable
        # names only; the "Relationship:" line is the canonical fixture.
        _anch = sorted({m.group(0) for m in _akrx.finditer(_blk)})
        check(f"no raw ANCHOR_ ids in {_name} block"
              + (f" — FOUND {_anch}" if _anch else ""), not _anch)

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
