"""Research-paper hypothesis intake — register #6, Phase C-1 (intake -> ticket -> triage -> test ->
verdict). NO publishing integration (that is C-2, later); no new corpus ingestion; no new measurement
types. Verdicts land in the /drafts queue as REVIEW ITEMS, never paste candidates.

SOURCES (zero-cost, ToS-clean — confirmed 2026-07-18 against https://info.arxiv.org/help/api/tou.html):
arXiv API only. Automated metadata/abstract harvesting is explicitly permitted (<=1 request / 3 s, single
connection); storing/serving full e-prints is NOT without copyright clearance — so this phase extracts
from ABSTRACTS ONLY and never downloads PDFs. SSRN has no legitimate free machine feed for new-paper
listings, so it is out — arXiv-only, stated plainly.

THE PRE-REGISTRATION RULE (the register's design note — what separates this from p-hacking with extra
steps): the hypothesis ticket is FIXED at extraction, BEFORE any measurement. The tester never adjusts a
ticket after seeing data; it only compares the frozen claim against the precomputed artifacts.

FABRICATION SURFACE — extraction is treated as HOSTILE (same spirit as the fidelity checker): the 12B can
misstate a paper's claim, and a wrong ticket tests a strawman. Every ticket carries a VERBATIM QUOTE of
the claim sentence(s); a deterministic consistency check requires the ticket's mapped assets and direction
to appear in that quote; anything failing sits UNVERIFIED and is never tested or presented as verified.

TESTING uses EXISTING machinery only (markets-llm read-only): pair fingerprints
(relational_pairs.json via relational_escalation.load_evidence), event studies (event_studies.json),
recovery stats (recovery_stats.json). A testable ticket that would need a new precompute is marked
NEEDS-EXTENSION — a demand signal, not a build.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path

import feedparser
import requests

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
MLL = Path(CFG["markets_llm_root"])
sys.path.insert(0, str(MLL / "generation"))

RESEARCH_CFG = CFG.get("research", {"enabled": False, "max_papers": 12,
                                    "categories": ["q-fin.GN", "q-fin.PM", "q-fin.ST", "q-fin.TR"]})

ARXIV_API = "http://export.arxiv.org/api/query"


# ============================ 1. intake (arXiv metadata only) ============================
def fetch_arxiv(max_papers: int | None = None, categories: list[str] | None = None) -> list[dict]:
    """One API request per run (well under the 1-per-3s limit): newest submissions in the configured
    q-fin categories. Returns [{id, title, abstract, published, link}] — metadata/abstract only."""
    cats = categories or RESEARCH_CFG.get("categories", ["q-fin.GN"])
    n = max_papers or RESEARCH_CFG.get("max_papers", 12)
    q = "+OR+".join(f"cat:{c}" for c in cats)
    url = (f"{ARXIV_API}?search_query={q}&sortBy=submittedDate&sortOrder=descending"
           f"&max_results={n}")
    r = requests.get(url, timeout=30, headers={"User-Agent": "content-agent-hypothesis-intake/0.1"})
    r.raise_for_status()
    feed = feedparser.parse(r.text)
    out = []
    for e in feed.entries:
        out.append({"id": e.get("id", "").rsplit("/", 1)[-1], "title": (e.get("title") or "").strip(),
                    "abstract": re.sub(r"\s+", " ", e.get("summary", "")).strip(),
                    "published": e.get("published", "")[:10],
                    "link": e.get("id", "")})
    return out


# ============================ 2. extraction (the 12B's job; hostile) ============================
_EXTRACT_PROMPT = """From the paper abstract below, extract AT MOST ONE testable market hypothesis as JSON.
Respond with ONLY a JSON object, no prose, with EXACTLY these keys:
  claim:      the paper's central testable claim in one plain-language sentence
  direction:  one of "positive" | "negative" | "inverse" | "outperform" | "underperform" |
              "predicts" | "none"
  assets:     list of the asset/factor NAMES the claim involves, as plain words from the abstract
              (e.g. ["bitcoin", "gold"], ["oil", "stocks"]) — [] if none
  conditions: regime/period/event conditions the claim depends on, "" if none stated
  quote:      the VERBATIM sentence(s) from the abstract that state the claim — copy exactly,
              character for character; never paraphrase inside quote
If the abstract makes no testable market claim (pure methodology, surveys, option pricing math),
return {"claim": "", "direction": "none", "assets": [], "conditions": "", "quote": ""}.

TITLE: {title}
ABSTRACT: {abstract}"""


def extract_ticket(paper: dict, chat=None) -> dict:
    """One frozen ticket per paper. The ticket IS the pre-registration: fixed here, before any
    measurement, and never edited afterward."""
    if chat is None:
        # LOW temperature: extraction is transcription-shaped work (frozen claim + VERBATIM quote), not
        # writing — the drafter's 0.7 produced paraphrased "quotes" that correctly failed the verbatim
        # check (first live cycle: inflated UNVERIFIED). 0.1 optimizes for faithfulness.
        from .studies import CFG as _cfg

        def chat(prompt):
            r = requests.post(f"{_cfg['drafting']['ollama_url']}/api/chat",
                              json={"model": _cfg["drafting"]["model"],
                                    "messages": [{"role": "user", "content": prompt}], "stream": False,
                                    "options": {"temperature": 0.1, "num_predict": 400}}, timeout=600)
            r.raise_for_status()
            return (r.json().get("message") or {}).get("content", "").strip()
    raw = chat(_EXTRACT_PROMPT.replace("{title}", paper["title"])
               .replace("{abstract}", paper["abstract"][:2400]))
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        j = json.loads(m.group(0)) if m else {}
    except Exception:
        j = {}
    return {"paper_id": paper["id"], "paper_title": paper["title"], "paper_date": paper["published"],
            "link": paper.get("link", ""),
            "claim": str(j.get("claim") or "").strip(),
            "direction": str(j.get("direction") or "none").strip().lower(),
            "assets": [str(a).strip().lower() for a in (j.get("assets") or []) if str(a).strip()],
            "conditions": str(j.get("conditions") or "").strip(),
            "quote": str(j.get("quote") or "").strip(),
            "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%S")}


# ============================ 3. triage (deterministic, never the model) ============================
_RECOVERY_TERMS = ("drawdown", "draw-down", "recovery", "recover", "crash", "correction", "selloff",
                   "sell-off", "bear market", "decline", "rebound")
_CROSS_SECTIONAL = ("cross-section", "cross section", "firm-level", "stock-level", "portfolio sort",
                    "sorted portfolio", "characteristic", "factor premium", "anomaly", "long-short")
_DIRECTIONAL_OK = ("positive", "negative", "inverse", "outperform", "underperform", "predicts")


def _event_vocab() -> dict:
    p = MLL / "deliverables" / "relational" / "event_studies.json"
    st = json.loads(p.read_text(encoding="utf-8")).get("studies", {}) if p.exists() else {}
    return {k: tuple(s.get("vocab", ())) for k, s in st.items()}


def triage(ticket: dict) -> dict:
    """TESTABLE only when the frozen claim maps onto EXISTING machinery. Everything else is UNTESTABLE
    with the reason — a high untestable rate is the truth of the engine's scope, not a failure."""
    from relational_escalation import _map_anchors
    text = " ".join([ticket.get("claim", ""), ticket.get("conditions", "")]).lower()
    if not ticket.get("claim"):
        return {"testable": False, "mode": None, "reason": "no testable market claim extracted"}
    if any(t in text for t in _CROSS_SECTIONAL):
        return {"testable": False, "mode": None,
                "reason": "cross-sectional/factor claim — needs per-stock data outside the engine's scope"}
    mapped = []
    for a in ticket.get("assets", []):
        mapped += [(al, nm) for al, nm in _map_anchors(a.lower()) if nm not in [m[1] for m in mapped]]
    anchors = [nm for _al, nm in mapped]
    ev_hit = next((k for k, vocab in _event_vocab().items() if any(v in text for v in vocab)), None)
    if ev_hit:
        return {"testable": True, "mode": "event", "event": ev_hit, "anchors": anchors or ["ANCHOR_SPY"],
                "mapped": mapped, "reason": f"registered event type {ev_hit}"}
    if len(anchors) >= 2:
        if ticket.get("direction") not in _DIRECTIONAL_OK:
            return {"testable": False, "mode": None, "mapped": mapped,
                    "reason": "two anchors but no comparable direction in the claim"}
        return {"testable": True, "mode": "pair", "anchors": anchors[:2], "mapped": mapped,
                "reason": f"anchor pair {anchors[0]} vs {anchors[1]}"}
    if len(anchors) == 1 and any(t in text for t in _RECOVERY_TERMS):
        return {"testable": True, "mode": "recovery", "anchors": anchors, "mapped": mapped,
                "reason": f"drawdown/recovery structure on {anchors[0]}"}
    if anchors:
        return {"testable": False, "mode": None, "mapped": mapped,
                "reason": "one mapped anchor, no event/recovery structure — no machinery fits"}
    return {"testable": False, "mode": None, "mapped": [],
            "reason": f"unmapped assets {ticket.get('assets')} — outside the anchor universe"}


# ============================ 4. consistency check (extraction is hostile) ============================
_DIR_LEXICON = {
    "positive": ("positive", "increase", "increases", "rise", "rises", "higher", "co-mov", "comov",
                 "correlat", "together", "amplif"),
    "negative": ("negative", "decreas", "fall", "falls", "lower", "declin", "drop", "reduc"),
    "inverse": ("invers", "opposite", "negative", "hedge", "diversif", "uncorrelat", "decoupl"),
    "outperform": ("outperform", "exceed", "beat", "higher return", "superior", "improvement over",
                   "improvements over", "gains over", "better than", "dominate"),
    "underperform": ("underperform", "lag", "trail", "lower return", "inferior",
                     # negated comparatives — "Gold has NOT been MORE efficient than crypto" IS an
                     # underperformance claim (first targeted live run)
                     "not more", "not been more", "less effective", "less efficient", "no better",
                     "no more effective", "no more efficient"),
    "predicts": ("predict", "forecast", "precede", "lead", "anticipat", "signal"),
}


def _canon(s: str) -> str:
    """Comparison canonicalization ONLY (the stored quote stays as extracted): lowercase, straighten curly
    quotes/dashes, collapse whitespace — so a whitespace or typography difference never fails a quote that
    IS verbatim in substance (observed in the first live cycle), while real paraphrase still fails."""
    s = (s or "").lower()
    for a, b in (("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"),
                 ("—", "-"), ("–", "-"), ("~", " ")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def consistency_check(ticket: dict, mapped: list) -> dict:
    """Deterministic: the ticket's mapped asset ALIASES and its direction's word family must appear in the
    VERBATIM quote. A ticket that fails sits UNVERIFIED — never tested, never presented as verified. The
    model's reading of the paper is not trusted unchecked."""
    quote = _canon(ticket.get("quote"))
    if not quote:
        return {"verified": False, "reason": "no verbatim quote extracted"}
    if ticket.get("_abstract") and quote not in _canon(ticket.get("_abstract")):
        return {"verified": False, "reason": "quote is not verbatim from the abstract"}
    missing = [al for al, _nm in mapped if al not in quote]
    if missing:
        return {"verified": False, "reason": f"mapped asset alias(es) {missing} absent from the quote"}
    d = ticket.get("direction", "none")
    if d in _DIR_LEXICON and not any(w in quote for w in _DIR_LEXICON[d]):
        return {"verified": False, "reason": f"direction '{d}' has no support words in the quote"}
    return {"verified": True, "reason": "assets + direction present in the verbatim quote"}


# ============================ 5. testing (existing artifacts only) ============================
def test_ticket(ticket: dict, tri: dict) -> dict:
    """Compare the FROZEN claim against precomputed artifacts. Verdicts: supported | contradicted |
    mixed | measured-context (no crisp sign to compare) | NEEDS-EXTENSION. Honesty labels ride along."""
    from relational_escalation import load_evidence, load_event_evidence, load_recovery_evidence
    labels = ["SURVIVORSHIP: survivor-only panel — stress co-movement understated",
              "SINGLE-INSTANCE: per-regime numbers are single instances, not distributions"]
    if tri["mode"] == "pair":
        ev = load_evidence(tuple(tri["anchors"]))
        if not ev:
            return {"verdict": "NEEDS-EXTENSION", "measured": None, "labels": [],
                    "note": f"pair {tri['anchors']} not precomputed — demand signal logged"}
        corr = ev.get("overall_corr")
        want_sign = {"positive": 1, "outperform": 1, "predicts": 0,
                     "negative": -1, "inverse": -1, "underperform": -1}.get(ticket["direction"], 0)
        if corr is None or want_sign == 0:
            verdict = "measured-context"
        elif abs(corr) < 0.05:
            verdict = "contradicted" if want_sign != 0 else "measured-context"
            labels.append(f"measured correlation ~0 ({corr:+.3f}) — claimed relationship not present "
                          "at daily frequency 2004-present")
        else:
            verdict = "supported" if (corr > 0) == (want_sign > 0) else "contradicted"
        eps = {k: v.get("corr") for k, v in (ev.get("episodes") or {}).items()}
        return {"verdict": verdict, "labels": labels,
                "measured": {"overall_corr": corr, "episodes": eps},
                "note": "sign comparison: claim direction vs full-period daily correlation + regimes"}
    if tri["mode"] == "event":
        st = load_event_evidence(tri["event"])
        if not st:
            return {"verdict": "NEEDS-EXTENSION", "measured": None, "labels": [],
                    "note": f"event {tri['event']} has no study artifact"}
        d = st.get("distribution", {})
        n = st.get("n_events")
        lab = ["SMALL-N: a handful of anecdotes, not a distribution"] if (n or 0) <= 15 else \
              ["LARGE-N: an empirical distribution"]
        return {"verdict": "measured-context", "labels": lab + ["FORWARD-LOOKING: inference, not prediction"],
                "measured": {"n_events": n, "depth": d.get("depth_pct"),
                             "recovery_months": d.get("recover_months")},
                "note": "event claims rarely reduce to one sign — the measured study is presented for "
                        "Bradley's comparison against the frozen claim"}
    if tri["mode"] == "recovery":
        r = load_recovery_evidence(tri["anchors"][0])
        if not r:
            return {"verdict": "NEEDS-EXTENSION", "measured": None, "labels": [],
                    "note": f"no recovery precompute for {tri['anchors'][0]}"}
        return {"verdict": "measured-context", "labels": labels[:1] + ["CENSORED where unrecovered"],
                "measured": {"summary": r.get("summary")},
                "note": "measured drawdown-recovery stats for comparison against the frozen claim"}
    return {"verdict": "NEEDS-EXTENSION", "measured": None, "labels": [], "note": "unknown mode"}


# ============================ 6. delivery (review items, queue-side) ============================
def _item_md(ticket: dict, tri: dict, cons: dict, result: dict | None) -> str:
    lines = [f"# [{'TESTED' if result else ('UNVERIFIED' if not cons.get('verified') else 'UNTESTABLE')}] "
             f"{ticket['paper_title'][:90]}",
             f"paper: {ticket['paper_id']} ({ticket['paper_date']}) · {ticket.get('link','')}",
             "", f"**Frozen claim (pre-registered):** {ticket['claim'] or '(none extracted)'}",
             f"**Direction:** {ticket['direction']} · **Assets:** {', '.join(ticket['assets']) or '—'}",
             f"**Verbatim quote:** \"{ticket['quote']}\"", "",
             f"**Consistency:** {'VERIFIED' if cons.get('verified') else 'UNVERIFIED'} — {cons.get('reason')}",
             f"**Triage:** {'TESTABLE (' + str(tri.get('mode')) + ')' if tri.get('testable') else 'UNTESTABLE'}"
             f" — {tri.get('reason')}"]
    if result:
        lines += ["", f"**VERDICT: {result['verdict']}** — {result.get('note','')}",
                  f"measured: {json.dumps(result.get('measured'), default=str)[:400]}"]
        lines += [f"- {l}" for l in result.get("labels", [])]
    return "\n".join(lines)


def run_nightly(max_papers: int | None = None, chat=None, quiet: bool = False) -> dict:
    """The full C-1 cycle: fetch -> extract -> consistency -> triage -> test -> queue. Returns the honest
    summary (papers, tickets, testable ratio with reasons, verdicts). GPU gating is the CALLER's job."""
    from . import queue_store as qs
    papers = fetch_arxiv(max_papers)
    # DEDUPE across nights: arXiv's newest-N window moves slowly, so without this every nightly would
    # re-create items for papers still in the window. A paper gets exactly one frozen ticket, ever.
    seen = set()
    for qp in qs.QUEUE.glob("*.json") if qs.QUEUE.exists() else []:
        try:
            qd = json.loads(qp.read_text(encoding="utf-8"))
            if qd.get("kind") == "research":
                seen.add(((qd.get("research") or {}).get("ticket") or {}).get("paper_id"))
        except Exception:
            continue
    new_papers = [p for p in papers if p["id"] not in seen]
    summary = {"papers": len(papers), "already_seen": len(papers) - len(new_papers),
               "tickets": 0, "no_claim": 0, "unverified": 0,
               "testable": 0, "untestable": 0, "reasons": {}, "verdicts": []}
    for p in new_papers:
        t = extract_ticket(p, chat=chat)
        t["_abstract"] = p["abstract"]
        if not t["claim"]:
            summary["no_claim"] += 1
            continue
        summary["tickets"] += 1
        tri = triage(t)
        cons = consistency_check(t, tri.get("mapped", []))
        result = None
        if not cons["verified"]:
            summary["unverified"] += 1
        elif tri["testable"]:
            summary["testable"] += 1
            result = test_ticket(t, tri)
            summary["verdicts"].append({"paper": t["paper_id"], "verdict": result["verdict"]})
        else:
            summary["untestable"] += 1
            summary["reasons"][tri["reason"]] = summary["reasons"].get(tri["reason"], 0) + 1
        t.pop("_abstract", None)
        qs.new_research_item(
            title=("[research] " + t["paper_title"][:70]),
            body_md=_item_md(t, tri, cons, result),
            payload={"ticket": t, "triage": tri, "consistency": cons, "result": result})
        if not quiet:
            state = "TESTED" if result else ("UNVERIFIED" if not cons["verified"] else "UNTESTABLE")
            print(f"  [{state:10}] {t['paper_id']} {t['paper_title'][:60]}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="one full nightly cycle (GPU: caller ensures free)")
    ap.add_argument("--max-papers", type=int, default=None)
    a = ap.parse_args()
    if a.run:
        s = run_nightly(a.max_papers)
        print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
