"""The artifact library — READ-ONLY consumer of markets-llm.

Reads engine artifacts in place and renders evidence via markets-llm's OWN canonical block builders
(generation/relational_escalation — stdlib-only module), so the evidence text drafts are built from is
byte-identical to what the thesis engine itself narrates, honesty labels included. Never writes anything
under markets-llm.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

CFG = json.loads((Path(__file__).resolve().parent.parent / "config" / "config.json")
                 .read_text(encoding="utf-8"))
MLL = Path(CFG["markets_llm_root"])
sys.path.insert(0, str(MLL / "generation"))
import relational_escalation as resc  # noqa: E402  (read-only import; loads artifacts lazily)


def _event_studies() -> dict:
    p = MLL / "deliverables" / "relational" / "event_studies.json"
    return json.loads(p.read_text(encoding="utf-8")).get("studies", {}) if p.exists() else {}


def _recovery_anchors() -> dict:
    p = MLL / "deliverables" / "relational" / "recovery_stats.json"
    return json.loads(p.read_text(encoding="utf-8")).get("anchors", {}) if p.exists() else {}


# priority order for the cadence fallback ("strongest unpublished study"): the event studies are the
# richest single-study spines; then the deepest-history recovery anchors.
LIBRARY_PRIORITY = [
    "event:midterm_election", "event:fomc_meeting", "event:pres_election",
    "recovery:ANCHOR_SPY", "recovery:ANCHOR_SMH", "recovery:ANCHOR_NASDAQ", "recovery:ANCHOR_XLK",
    "recovery:ANCHOR_XLF", "recovery:ANCHOR_GOLD", "recovery:ANCHOR_XLE", "recovery:ANCHOR_OIL_WTI",
]


def list_library() -> list[str]:
    ids = [f"event:{k}" for k in _event_studies()] + [f"recovery:{a}" for a in _recovery_anchors()]
    ranked = [s for s in LIBRARY_PRIORITY if s in ids]
    return ranked + [s for s in ids if s not in ranked]


def evidence_for(study_id: str) -> dict | None:
    """-> {study_id, title_hint, evidence (canonical block text), provenance} or None."""
    kind, _, key = study_id.partition(":")
    if kind == "event":
        st = _event_studies().get(key)
        if not st:
            return None
        return {"study_id": study_id,
                "title_hint": f"{st.get('event_type')} on {st.get('asset_label')}",
                "evidence": resc.build_event_block(key, st),
                "provenance": {"artifact": "deliverables/relational/event_studies.json",
                               "study_key": key, "n_events": st.get("n_events")}}
    if kind == "recovery":
        entry = _recovery_anchors().get(key)
        if not entry:
            return None
        return {"study_id": study_id,
                "title_hint": f"drawdown & recovery — {entry.get('proxy') or key.replace('ANCHOR_', '')}",
                "evidence": resc.build_recovery_block(key, entry),
                "provenance": {"artifact": "deliverables/relational/recovery_stats.json",
                               "study_key": key, "proxy": entry.get("proxy")}}
    if kind == "pair":
        pair = tuple(key.split("|"))
        ev = resc.load_evidence(pair)
        if not ev:
            return None
        return {"study_id": study_id,
                "title_hint": f"measured relationship — {pair[0].replace('ANCHOR_','')} vs {pair[1].replace('ANCHOR_','')}",
                "evidence": resc.build_evidence_block(pair, ev),
                "provenance": {"artifact": "deliverables/relational/relational_pairs.json",
                               "study_key": key}}
    return None
