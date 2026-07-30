"""Chart module self-test — deterministic, NO GPU, NO network, hermetic (fixture artifacts + synthetic
prices). Joins the standing test suite. Asserts STRUCTURAL properties of each rendered template, because a
chart's fidelity is structural (pure function of artifact -> pixels), never model-checked.

  .venv/Scripts/python.exe scripts/chart_selftest.py

Renders all three templates from FIXTURE data (the module's _studies() and price cache are monkeypatched to
in-memory fixtures) into a temp dir, then asserts:
  - overlay: line count == event count; every event labeled; footer present; election markers at the correct
    x-positions (each in the early-November band of a Jul-1-anchored half).
  - sector bars: bar count == sector count; SPY highlighted; NOT-A-RANKING on the face; footer.
  - FOMC histogram: value count == event count; median marked; footer.
  - every PNG exists and is a non-trivial image.
"""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd                              # noqa: E402
from content_agent import charts                 # noqa: E402

# --- fixtures ------------------------------------------------------------------------------------------
FIX_YEARS = [2006, 2010, 2014, 2018, 2022]       # same five the module knows


def _fixture_prices() -> pd.DataFrame:
    """Synthetic daily SPY covering H2 of each fixture year — a gentle deterministic ramp so the render has
    real shape without depending on markets-llm price data."""
    idx = pd.DatetimeIndex([])
    vals = []
    for k, y in enumerate(FIX_YEARS):
        days = pd.date_range(f"{y}-07-01", f"{y}-12-31", freq="B")
        base = 100.0 + k                          # distinct level per year
        series = base * (1 + 0.0004 * pd.RangeIndex(len(days)))   # slow ramp
        idx = idx.append(days)
        vals.extend(series.tolist())
    return pd.DataFrame({"ANCHOR_SPY": vals}, index=idx)


def _fixture_studies() -> dict:
    sectors = {
        "ANCHOR_SPY": {"label": "the US stock market (SPY)", "n_events": 5,
                       "distribution": {"depth_pct": {"median": -15.7}, "recover_months": {"median": 3.6}}},
        "ANCHOR_SMH": {"label": "semiconductors (SMH ETF proxy)", "n_events": 5,
                       "distribution": {"depth_pct": {"median": -27.0}, "recover_months": {"median": 3.3}}},
        "ANCHOR_XLP": {"label": "consumer staples (XLP ETF proxy)", "n_events": 5,
                       "distribution": {"depth_pct": {"median": -8.9}, "recover_months": {"median": 2.5}}},
    }
    fomc_events = [{"event": f"20{8+i:02d}-01-01", "depth_pct": round(-2 - (i % 30), 1)} for i in range(166)]
    fomc_events[0]["depth_pct"] = -35.0
    fomc_events[0]["event"] = "2008-10-29"
    fomc_events[1]["depth_pct"] = -33.7
    fomc_events[1]["event"] = "2020-03-15"
    return {
        "midterm_election": {"event_type": "US midterm elections", "n_events": 5,
                             "events": [{"event": f"{y}-11-05", "depth_pct": -15.0,
                                         "onset_vs_event_months": -6.0, "trough_vs_event_months": -1.0,
                                         "peak_date": f"{y}-05-01", "trough_date": f"{y}-10-01",
                                         "recover_months": 3.0, "censored": False} for y in FIX_YEARS],
                             "sectors": sectors},
        "fomc_meeting": {"event_type": "US Federal Reserve (FOMC) meetings", "n_events": 166,
                         "events": fomc_events,
                         "distribution": {"depth_pct": {"median": -4.2, "min": -35.0, "max": -0.7}}},
    }


def main():
    charts._PRICE_CACHE["lv"] = _fixture_prices()
    charts._studies = _fixture_studies              # monkeypatch the artifact reader
    tmp = Path(tempfile.mkdtemp(prefix="chart_selftest_"))
    ok, checks = True, []

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        checks.append((bool(cond), name))

    # T1 overlay
    m = charts.chart_midterm_overlay(tmp / "overlay.png")
    check("overlay: line count == event count (5)", m["n_lines"] == len(FIX_YEARS))
    check("overlay: every event labeled", sorted(m["labeled_events"]) == sorted(FIX_YEARS))
    check("overlay: footer present", m["has_footer"])
    check("overlay: 5 election markers", m["n_election_markers"] == len(FIX_YEARS))
    check("overlay: election markers in early-Nov band (day 120-135 of half)",
          all(120 <= d <= 135 for d in m["election_days_of_half"]))
    check("overlay: PNG non-trivial", (tmp / "overlay.png").stat().st_size > 10000)

    # T2 sector bars
    m2 = charts.chart_sector_dispersion("midterm_election", tmp / "sectors.png")
    check("sector: bar count == sector count (3 fixture)", m2["n_bars"] == 3)
    check("sector: SPY highlighted", m2["spy_highlighted"])
    check("sector: NOT-A-RANKING on face", m2["not_a_ranking_on_face"])
    check("sector: SECTOR-PROXY tickers present (SPY/SMH/XLP)",
          set(m2["tickers"]) == {"SPY", "SMH", "XLP"})
    check("sector: footer present", m2["has_footer"])
    check("sector: PNG non-trivial", (tmp / "sectors.png").stat().st_size > 10000)

    # T3 FOMC histogram
    m3 = charts.chart_fomc_distribution("fomc_meeting", tmp / "fomc.png")
    check("fomc: value count == event count (166)", m3["n_values"] == 166 and m3["n_events"] == 166)
    check("fomc: median marked", m3["median_marked"])
    check("fomc: footer present", m3["has_footer"])
    check("fomc: PNG non-trivial", (tmp / "fomc.png").stat().st_size > 8000)

    # T5 pair regime fingerprint (2026-07-29) — structural assertions, not pixel comparison
    m5 = charts.chart_pair_regimes("ANCHOR_RATE_10Y|ANCHOR_SPY", tmp / "pair_flip.png")
    import sys as _s
    from content_agent.studies import MLL as _MLL
    _s.path.insert(0, str(_MLL / "generation"))
    import relational_escalation as _resc
    _ev = _resc.load_evidence(("ANCHOR_RATE_10Y", "ANCHOR_SPY"))
    _n_eps = sum(1 for d in _ev["episodes"].values() if d.get("corr") is not None)
    check(f"pair: bar count == measured episode count ({_n_eps})", m5["n_bars"] == _n_eps)
    check("pair: full-period reference line present", m5["reference_line"] is True)
    check("pair: overall corr matches the artifact", m5["overall_corr"] == _ev["overall_corr"])
    check("pair: the sign flip is detected (bars cross zero)", m5["crosses_zero"] is True)
    check("pair: SINGLE-INSTANCE stated on the face", m5["single_instance_on_face"])
    check("pair: SURVIVORSHIP stated (this pair's evidence carries it)", m5["survivorship_on_face"])
    check("pair: n-days present for every bar",
          len(m5["n_days"]) == m5["n_bars"] and all(isinstance(x, int) for x in m5["n_days"]))
    check("pair: labels are READABLE, not internal keys",
          all("_" not in l for l in m5["labels"]) and any("2022" in l for l in m5["labels"]))
    check("pair: footer present", m5["has_footer"])
    check("pair: PNG non-trivial", (tmp / "pair_flip.png").stat().st_size > 8000)
    # a pair with no sign flip must NOT report one (both directions)
    m5b = charts.chart_pair_regimes("ANCHOR_XLE|ANCHOR_XLK", tmp / "pair_noflip.png")
    check("pair: an all-positive pair does not report crossing zero", m5b["crosses_zero"] is False)
    # the <2-episode guard, asserted on a SYNTHETIC one-episode pair so the test cannot silently
    # pass because the real artifact happens to be rich (an "or True" here was a tautology).
    _real_load = _resc.load_evidence
    _resc.load_evidence = lambda p: {"overall_corr": 0.5, "episodes": {
        "crash_2008": {"corr": 0.8, "n_days": 146}, "covid_2020": {"corr": None, "n_days": 0}}}
    check("pair: <2 measured episodes -> no chart (decoration refused)",
          charts.chart_pair_regimes("ANCHOR_X|ANCHOR_Y", tmp / "pair_thin.png") is None)
    _resc.load_evidence = _real_load
    from content_agent import charts as _c
    check("pair: unknown pair key -> None, never a broken render",
          _c.chart_pair_regimes("ANCHOR_NOPE|ANCHOR_ALSONOPE", tmp / "pair_x.png") is None)

    # DISPLAY-NAME MAP — every episode key the builders can emit has a readable name
    _keys = set()
    import json as _json
    _pairs = _json.loads((_MLL / "deliverables" / "relational" / "relational_pairs.json")
                         .read_text(encoding="utf-8"))["pairs"]
    for _v in _pairs.values():
        _keys |= set((_v.get("episodes") or {}).keys()) | set((_v.get("hmm_regimes") or {}).keys())
    _rec = _json.loads((_MLL / "deliverables" / "relational" / "recovery_stats.json")
                       .read_text(encoding="utf-8"))["anchors"]
    for _v in _rec.values():
        _keys |= {d.get("trough_regime") for d in _v.get("drawdowns", []) if d.get("trough_regime")}
        _keys |= set((_v.get("summary", {}).get("notable") or {}).keys())
    _unmapped = sorted(k for k in _keys if k and k not in _resc._EPISODE_DISPLAY)
    check(f"display-map covers every emitted episode key ({len(_keys)} keys)"
          + (f" — UNMAPPED {_unmapped}" if _unmapped else ""), not _unmapped)
    check("unmapped key still never renders as a raw identifier",
          "_" not in _resc._epd("some_future_regime_2031"))

    # RENDERER — exactly one H1 in a flagship artifact (the duplicated-H1 fix)
    from content_agent.publisher import ManualFallbackAdapter
    import re as _re5
    _res = ManualFallbackAdapter().publish_post("Test Title", "measured, not predicted",
                                                "# Test Title\n\nBody paragraph here.")
    _txt = Path(_res["url_or_path"]).read_text(encoding="utf-8")
    check("renderer: exactly one H1 when the body carries its own",
          len(_re5.findall(r"(?m)^# ", _txt)) == 1)
    check("renderer: subtitle still present", "*measured, not predicted*" in _txt)
    check("renderer: body content preserved", "Body paragraph here." in _txt)
    _res2 = ManualFallbackAdapter().publish_post("Headless Piece", "sub", "Just a body, no heading.")
    _txt2 = Path(_res2["url_or_path"]).read_text(encoding="utf-8")
    check("renderer: H1 still added when the body lacks one",
          len(_re5.findall(r"(?m)^# ", _txt2)) == 1 and "# Headless Piece" in _txt2)
    for _p in (_res["url_or_path"], _res2["url_or_path"]):
        Path(_p).unlink(missing_ok=True)
        Path(_p).with_suffix(".html").unlink(missing_ok=True)

    print("CHART SELF-TEST (hermetic; fixtures + synthetic prices; no GPU/network)\n")
    for good, name in checks:
        print(f"  {'OK ' if good else 'XX '} {name}")
    passed = sum(g for g, _ in checks)
    print(f"\nSELF-TEST: {passed}/{len(checks)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
