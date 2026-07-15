"""Deterministic chart module — code renders charts from engine artifacts, NEVER the model.

Fidelity is STRUCTURAL, not checked: a chart is a pure function (artifact JSON + price data -> PNG). No LLM
anywhere in the render path; same inputs, same pixels. The drafter is never told a chart's contents, so
there is nothing new for it to fabricate — charts and prose are independent renderings of the same
artifact.

HONESTY IS RENDERED, not captioned:
  - SMALL-N  -> show every line/event individually, never an average-only view (the overlay IS the label).
  - SECTOR-PROXY -> the ETF ticker appears ON the chart (bars/labels).
  - NOT-A-RANKING -> stated on the chart face as a subtitle.
  - LARGE-N -> the distribution view SMALL-N is denied (histogram).
  - PROVENANCE travels with the picture: source + window + generation date in a footer on EVERY image,
    because charts get screenshotted away from their article.

Data (READ-ONLY from markets-llm):
  - artifacts: deliverables/relational/event_studies.json (same file studies.py reads).
  - daily prices: relational/engine.load_anchor_levels() — the canonical anchor price loader
    (needs pandas+pyarrow, installed into this venv; see the module docstring in charts_selftest).
"""
from __future__ import annotations
import datetime as _dt
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                       # headless, CPU-only, deterministic
import matplotlib.dates as mdates           # noqa: E402
import matplotlib.pyplot as plt             # noqa: E402
import pandas as pd                         # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
MLL = Path(CFG["markets_llm_root"])
OUT_CHARTS = ROOT / "out" / "charts"
PUB_NAME = CFG["publisher"].get("publication_name", "Akribeia Insights")

# --- house style: clean, light, serious; no chartjunk (reads on Substack white + when screenshotted) ---
INK = "#1a1f2b"
MUTE = "#6b7280"
GRID = "#e5e7eb"
BASELINE = "#111827"
ACCENT = "#b45309"          # muted amber for the highlighted/baseline series
EVENT_LINE = "#9aa0aa"
# a distinguishable, print-safe categorical palette (colour-blind-aware, no near-duplicates)
PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#e6a01f", "#17becf", "#8c564b", "#7f7f7f"]

MIDTERM_DAYS = {2006: "2006-11-07", 2010: "2010-11-02", 2014: "2014-11-04",
                2018: "2018-11-06", 2022: "2022-11-08"}
_PRICE_CACHE = {"lv": None}


def _house():
    plt.rcParams.update({
        "figure.dpi": 150, "savefig.dpi": 150, "figure.facecolor": "white",
        "axes.facecolor": "white", "axes.edgecolor": GRID, "axes.labelcolor": INK,
        "axes.titlecolor": INK, "text.color": INK, "xtick.color": MUTE, "ytick.color": MUTE,
        "font.family": "DejaVu Sans", "font.size": 11, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    })


def _prices():
    if _PRICE_CACHE["lv"] is None:
        sys.path.insert(0, str(MLL / "relational"))
        import engine
        _PRICE_CACHE["lv"], _ = engine.load_anchor_levels(pd.Timestamp.today().normalize())
    return _PRICE_CACHE["lv"]


def _studies() -> dict:
    p = MLL / "deliverables" / "relational" / "event_studies.json"
    return json.loads(p.read_text(encoding="utf-8")).get("studies", {}) if p.exists() else {}


def _footer(fig, source: str, window: str):
    gen = _dt.date.today().isoformat()
    fig.text(0.5, 0.012, f"{PUB_NAME}   ·   {source}   ·   window {window}   ·   generated {gen}",
             ha="center", va="bottom", fontsize=8, color=MUTE)


def _save(fig, out_path: Path) -> Path:
    OUT_CHARTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.3, facecolor="white")
    plt.close(fig)
    return out_path


# ======================================================================================================
# Template 1 — the midterm overlay (the launch chart). SMALL-N made visual: five lines, each visible.
# ======================================================================================================
def chart_midterm_overlay(out_path: Path | None = None) -> dict:
    """Second-half-of-year (Jul 1–Dec 31) SPY for each of the five midterm years, each normalized to 100 at
    the window start, superimposed and aligned by calendar position, election day marked, each line labeled
    by year. Every line individually visible — this IS the SMALL-N label. Returns structural metadata."""
    out_path = out_path or (OUT_CHARTS / "midterm_overlay_spy_h2.png")
    _house()
    spy = _prices()["ANCHOR_SPY"].dropna()
    fig, ax = plt.subplots(figsize=(9, 5.4))
    ref = pd.Timestamp("2000-07-01")               # common x reference (year stripped) so H2 lines align
    labeled, elec_x = [], []
    for i, (yr, eday) in enumerate(sorted(MIDTERM_DAYS.items())):
        w = spy.loc[f"{yr}-07-01":f"{yr}-12-31"]
        if w.empty:
            continue
        norm = w / w.iloc[0] * 100.0
        x = [ref + pd.Timedelta(days=(d - pd.Timestamp(f"{yr}-07-01")).days) for d in norm.index]
        col = PALETTE[i % len(PALETTE)]
        ax.plot(x, norm.values, color=col, lw=1.7, label=str(yr), alpha=0.95)
        # end-of-line year label + election dot on this line
        ax.annotate(str(yr), (x[-1], norm.values[-1]), color=col, fontsize=9, fontweight="bold",
                    xytext=(4, 0), textcoords="offset points", va="center")
        e = pd.Timestamp(eday)
        ex = ref + pd.Timedelta(days=(e - pd.Timestamp(f"{yr}-07-01")).days)
        ey = norm.loc[:eday].iloc[-1]
        ax.plot([ex], [ey], marker="o", ms=4.5, color=col, zorder=5)
        elec_x.append(ex)
        labeled.append(yr)
    # election marker: a vertical line at the mean election calendar position + 'Election' tag
    mean_elec = ref + pd.Timedelta(days=int(sum((x - ref).days for x in elec_x) / len(elec_x)))
    ax.axvline(mean_elec, color=EVENT_LINE, lw=1.0, ls="--", zorder=1)
    ax.text(mean_elec, ax.get_ylim()[1], " Election Day", color=MUTE, fontsize=8.5, va="top", ha="left")
    ax.axhline(100, color=GRID, lw=1.0, zorder=0)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_ylabel("SPY, indexed to 100 at Jul 1")
    ax.set_title("How the S&P 500 traded in the second half of each midterm year",
                 fontsize=13, fontweight="bold", loc="left", pad=30)
    ax.text(0, 1.045, "Each half-year indexed to 100 — all five shown (SMALL-N: a handful, not a "
            "distribution)", transform=ax.transAxes, fontsize=8.5, color=MUTE, va="bottom")
    ax.legend(loc="upper left", frameon=False, fontsize=9, ncol=5, columnspacing=1.2,
              bbox_to_anchor=(0, 0.99))
    _footer(fig, "relational engine (markets-llm); SPY = m5_gold_equity spy_close",
            "Jul 1–Dec 31 of 2006/2010/2014/2018/2022")
    _save(fig, out_path)
    # election day-of-half for each year (days since Jul 1) — used by the self-test to assert markers land
    # in the early-November band (~day 123-131 of a Jul-1-anchored half).
    elec_doh = [int((pd.Timestamp(MIDTERM_DAYS[y]) - pd.Timestamp(f"{y}-07-01")).days) for y in labeled]
    return {"template": "midterm_overlay", "path": str(out_path), "n_lines": len(labeled),
            "labeled_events": labeled, "n_election_markers": len(elec_x), "has_footer": True,
            "election_days_of_half": elec_doh}


# ======================================================================================================
# Template 2 — sector dispersion (piece #2): ranked horizontal bars of per-sector midterm median depth.
# ======================================================================================================
def chart_sector_dispersion(event_key: str = "midterm_election", out_path: Path | None = None) -> dict:
    out_path = out_path or (OUT_CHARTS / f"sector_dispersion_{event_key}.png")
    _house()
    st = _studies().get(event_key, {})
    sectors = st.get("sectors", {})
    rows = []
    for anc, cell in sectors.items():
        med = ((cell.get("distribution", {}) or {}).get("depth_pct") or {}).get("median")
        if med is None:
            continue
        label = cell.get("label", anc)
        ticker = "SPY" if anc == "ANCHOR_SPY" else anc.replace("ANCHOR_", "")
        rows.append((ticker, label, med, anc == "ANCHOR_SPY"))
    rows.sort(key=lambda r: r[2])                    # deepest (most negative) first -> bottom-to-top
    tickers = [r[0] for r in rows]
    vals = [r[2] for r in rows]
    colors = [ACCENT if r[3] else "#3b6fa0" for r in rows]
    fig, ax = plt.subplots(figsize=(9, 6))
    y = range(len(rows))
    ax.barh(list(y), vals, color=colors, height=0.68)
    for yi, (tk, lab, v, is_spy) in zip(y, rows):
        ax.text(v - 0.4, yi, f"{v:.1f}%  {tk}" + ("  (baseline)" if is_spy else ""),
                va="center", ha="right", fontsize=9,
                color=BASELINE if is_spy else INK, fontweight="bold" if is_spy else "normal")
    ax.set_yticks(list(y))
    ax.set_yticklabels([r[1].replace(" ETF proxy", "").replace(" (", "\n(") for r in rows], fontsize=8.5)
    ax.set_xlabel("median peak-to-trough drawdown, %")
    ax.invert_xaxis()                                # deeper (more negative) extends left
    n = st.get("n_events", 5)
    ax.set_title("Inside the same five midterm windows, the sectors were not moving together",
                 fontsize=13, fontweight="bold", loc="left", pad=30)
    ax.text(0, 1.03, f"Median depth, {n} midterm windows · ETF SECTOR-PROXY · NOT-A-RANKING: past "
            "dispersion, not a forecast", transform=ax.transAxes, fontsize=8.5, color=MUTE, va="bottom")
    _footer(fig, "relational engine (markets-llm); sector ETF proxies",
            "5 midterms 2006–2022; SPY 2004-present")
    _save(fig, out_path)
    return {"template": "sector_dispersion", "path": str(out_path), "n_bars": len(rows),
            "spy_highlighted": any(r[3] for r in rows), "tickers": tickers, "has_footer": True,
            "not_a_ranking_on_face": True}


# ======================================================================================================
# Template 3 — distribution view (FOMC): 166-event drawdown-depth histogram. LARGE-N gets the view SMALL-N
# is denied — the N-adaptive honesty pattern, now visual.
# ======================================================================================================
def chart_fomc_distribution(event_key: str = "fomc_meeting", out_path: Path | None = None) -> dict:
    out_path = out_path or (OUT_CHARTS / "fomc_depth_distribution.png")
    _house()
    st = _studies().get(event_key, {})
    depths = [e["depth_pct"] for e in st.get("events", []) if e.get("depth_pct") is not None]
    dist = st.get("distribution", {})
    med = (dist.get("depth_pct") or {}).get("median")
    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.hist(depths, bins=28, color="#3b6fa0", edgecolor="white", linewidth=0.5)
    if med is not None:
        ax.axvline(med, color=ACCENT, lw=1.8)
        ax.text(med, ax.get_ylim()[1] * 0.96, f" median {med}%", color=ACCENT, fontsize=9.5,
                va="top", ha="left", fontweight="bold")
    # annotate the crisis tail (deepest events), staggered so the two labels never collide
    tail = sorted((e for e in st.get("events", []) if e.get("depth_pct") is not None),
                  key=lambda e: e["depth_pct"])[:2]
    for j, e in enumerate(tail):
        yr = e["event"][:4]
        ax.annotate(f"{yr}: {e['depth_pct']}%", (e["depth_pct"], 1), textcoords="offset points",
                    xytext=(6, 34 + j * 26), ha="left", fontsize=8.5, color=MUTE,
                    arrowprops=dict(arrowstyle="->", color=MUTE, lw=0.8))
    ax.set_xlabel("peak-to-trough drawdown around the meeting, %")
    ax.set_ylabel("number of meetings")
    n = st.get("n_events", len(depths))
    ax.set_title("Drawdowns around Fed meetings are a distribution, not an anecdote",
                 fontsize=13, fontweight="bold", loc="left", pad=30)
    ax.text(0, 1.03, f"{n} FOMC meetings since 2004 (±1mo) · LARGE-N: an empirical distribution; the "
            "2008/2020 tails dwarf the median", transform=ax.transAxes, fontsize=8.5, color=MUTE,
            va="bottom")
    _footer(fig, "relational engine (markets-llm); SPY around FOMC dates", "2004-present; ±1 month/meeting")
    _save(fig, out_path)
    return {"template": "fomc_distribution", "path": str(out_path), "n_values": len(depths),
            "n_events": n, "median_marked": med is not None, "has_footer": True}


CHART_BUILDERS = {
    "midterm_overlay": chart_midterm_overlay,
    "sector_dispersion": chart_sector_dispersion,
    "fomc_distribution": chart_fomc_distribution,
}
