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
    """-> {study_id, title_hint, evidence (canonical block text), provenance} or None.

    Study-id forms:
      event:<key>            -> the SPY-level per-event study (build_event_block)
      sector_event:<key>     -> the SECTOR-BY-SECTOR comparative for that event (build_sector_event_block,
                                mode 'all') — the dispersion-across-sectors material.
    """
    kind, _, key = study_id.partition(":")
    if kind == "sector_event":
        st = _event_studies().get(key)
        if not st or not st.get("sectors"):
            return None
        scope = {"scoped": True, "mode": "all", "anchors": []}
        return {"study_id": study_id,
                "title_hint": f"cross-sector dispersion around {st.get('event_type')}",
                "evidence": resc.build_sector_event_block(key, st, scope),
                "provenance": {"artifact": "deliverables/relational/event_studies.json",
                               "study_key": key, "n_events": st.get("n_events"),
                               "view": "sector_comparative", "n_sectors": len(st.get("sectors", {}))}}
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
    if kind == "digest":
        # THE DAILY MEASURED DIGEST. key is a session date ("2026-07-23") or "" for the latest settled
        # one. Assembly and rendering both live in markets-llm (generation/digest_core), same law as
        # every other block: the evidence a draft is built from is what the engine itself would say.
        # Citations are attached here, from content-agent's primary-source layer, and are VERBATIM.
        sys.path.insert(0, str(MLL / "generation"))
        import digest_core as dc
        try:
            digest = dc.build_digest(key or None)
        except (FileNotFoundError, ValueError):
            return None
        try:
            from .attribution import citations_for
            digest["citations"] = citations_for(digest["as_of"])
        except Exception:
            digest["citations"] = []      # no primary source found is a normal outcome: omit, never invent
        lead = digest["lead"]
        n_cross = len(digest["crossings"])
        return {"study_id": f"digest:{digest['as_of']}",
                "title_hint": (f"measured session digest — {digest['as_of']}"
                               + (f", {n_cross} threshold crossing(s)" if n_cross
                                  else ", sector dispersion")),
                "evidence": dc.build_digest_block(digest),
                "digest": digest,
                "provenance": {"artifact": "deliverables/relational/conditional_stats.json",
                               "study_key": digest["as_of"], "lead": lead, "crossings": n_cross,
                               "substrate": "yahoo", "citations": len(digest["citations"])}}
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
