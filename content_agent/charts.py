"""Deterministic chart module — code renders charts from engine artifacts, NEVER the model.

THIN WRAPPER (2026-07-16): the render templates moved to markets-llm generation/chart_core.py (register #5
graduation — the /m thesis path consumes the same implementation). This module keeps content-agent's data
loading (read-only from markets-llm), output paths, and publication branding, and passes them to the shared
core. Same public API as before: chart_midterm_overlay / chart_sector_dispersion / chart_fomc_distribution
/ CHART_BUILDERS; renders are byte-stable vs the pre-relocation templates (hash-verified same-day).

Fidelity is STRUCTURAL, not checked: a chart is a pure function (artifact JSON + price data -> PNG). No LLM
anywhere in the render path; same inputs, same pixels. The drafter is never told a chart's contents.
See chart_core's docstring for the rendered-honesty rules (SMALL-N overlay, LARGE-N histogram,
SECTOR-PROXY/NOT-A-RANKING on the face, coverage gaps on the face, provenance footer).

Data (READ-ONLY from markets-llm):
  - artifacts: deliverables/relational/event_studies.json (same file studies.py reads).
  - daily prices: relational/engine.load_anchor_levels() — the canonical anchor price loader.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
MLL = Path(CFG["markets_llm_root"])
OUT_CHARTS = ROOT / "out" / "charts"
PUB_NAME = CFG["publisher"].get("publication_name", "Akribeia Insights")

sys.path.insert(0, str(MLL / "generation"))
import chart_core  # noqa: E402  (markets-llm hosts; content-agent imports — same direction as engine)

MIDTERM_DAYS = {2006: "2006-11-07", 2010: "2010-11-02", 2014: "2014-11-04",
                2018: "2018-11-06", 2022: "2022-11-08"}
_PRICE_CACHE = {"lv": None}


def _prices():
    if _PRICE_CACHE["lv"] is None:
        sys.path.insert(0, str(MLL / "relational"))
        import engine
        _PRICE_CACHE["lv"], _ = engine.load_anchor_levels(pd.Timestamp.today().normalize())
    return _PRICE_CACHE["lv"]


def _studies() -> dict:
    p = MLL / "deliverables" / "relational" / "event_studies.json"
    return json.loads(p.read_text(encoding="utf-8")).get("studies", {}) if p.exists() else {}


# ======================================================================================================
# Template 1 — the midterm overlay (the launch chart). SMALL-N made visual: five lines, each visible.
# ======================================================================================================
def chart_midterm_overlay(out_path: Path | None = None) -> dict:
    """Second-half-of-year (Jul 1–Dec 31) SPY for each of the five midterm years — see
    chart_core.chart_event_overlay. Returns structural metadata."""
    out_path = out_path or (OUT_CHARTS / "midterm_overlay_spy_h2.png")
    return chart_core.chart_event_overlay(
        _prices(), MIDTERM_DAYS, out_path=out_path, pub_name=PUB_NAME,
        source="relational engine (markets-llm); SPY = m5_gold_equity spy_close",
        window_label="Jul 1–Dec 31 of 2006/2010/2014/2018/2022",
        title="How the S&P 500 traded in the second half of each midterm year",
        subtitle="Each half-year indexed to 100 — all five shown (SMALL-N: a handful, not a "
                 "distribution)",
        anchors=[("ANCHOR_SPY", "SPY")], ylabel="SPY, indexed to 100 at Jul 1",
        template_name="midterm_overlay")


# ======================================================================================================
# Template 2 — sector dispersion (piece #2): ranked horizontal bars of per-sector midterm median depth.
# ======================================================================================================
def chart_sector_dispersion(event_key: str = "midterm_election", out_path: Path | None = None) -> dict:
    out_path = out_path or (OUT_CHARTS / f"sector_dispersion_{event_key}.png")
    st = _studies().get(event_key, {})
    n = st.get("n_events", 5)
    return chart_core.chart_sector_dispersion(
        st, out_path=out_path, pub_name=PUB_NAME,
        source="relational engine (markets-llm); sector ETF proxies",
        window_label="5 midterms 2006–2022; SPY 2004-present",
        title="Inside the same five midterm windows, the sectors were not moving together",
        subtitle=f"Median depth, {n} midterm windows · ETF SECTOR-PROXY · NOT-A-RANKING: past "
                 "dispersion, not a forecast",
        template_name="sector_dispersion")


# ======================================================================================================
# Template 3 — distribution view (FOMC): 166-event drawdown-depth histogram.
# ======================================================================================================
def chart_fomc_distribution(event_key: str = "fomc_meeting", out_path: Path | None = None) -> dict:
    out_path = out_path or (OUT_CHARTS / "fomc_depth_distribution.png")
    st = _studies().get(event_key, {})
    depths = [e["depth_pct"] for e in st.get("events", []) if e.get("depth_pct") is not None]
    n = st.get("n_events", len(depths))
    return chart_core.chart_event_distribution(
        st, out_path=out_path, pub_name=PUB_NAME,
        source="relational engine (markets-llm); SPY around FOMC dates",
        window_label="2004-present; ±1 month/meeting",
        title="Drawdowns around Fed meetings are a distribution, not an anecdote",
        subtitle=f"{n} FOMC meetings since 2004 (±1mo) · LARGE-N: an empirical distribution; the "
                 "2008/2020 tails dwarf the median",
        template_name="fomc_distribution")


CHART_BUILDERS = {
    "midterm_overlay": chart_midterm_overlay,
    "sector_dispersion": chart_sector_dispersion,
    "fomc_distribution": chart_fomc_distribution,
}
