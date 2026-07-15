"""Review-queue persistence + the autonomy flag (ships OFF; flip criteria in code, not vibes).

Streak rules (encoded, visible in the UI):
  - Approve with edit_class in (none, taste)  -> streak += 1   (taste edits don't count against)
  - Approve with edit_class == correctness    -> streak = 0    (correctness edits reset)
  - Reject                                    -> streak = 0    (breaks "consecutive approvals")
  - streak >= required_streak (config, 12)    -> autonomy flips ON automatically, logged
  - TRIPWIRE: a post-publication factual correction -> autonomy OFF + streak 0, logged
FAILED-FIDELITY drafts cannot be approved (server enforces Edit -> re-check -> pass first).
"""
from __future__ import annotations
import datetime as dt
import json
import threading
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "queue"
STATE = ROOT / "state"
STATE_FILE = STATE / "state.json"
AUDIT = STATE / "audit_log.jsonl"
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
_LOCK = threading.Lock()

_DEFAULT_STATE = {"streak": 0, "autonomy_enabled": False, "last_flagship_ts": 0.0,
                  "published_study_ids": [], "results_watermark": 0.0}


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def load_state() -> dict:
    if STATE_FILE.exists():
        return {**_DEFAULT_STATE, **json.loads(STATE_FILE.read_text(encoding="utf-8"))}
    return dict(_DEFAULT_STATE)


def save_state(st: dict):
    STATE.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def log(event: str, **kw):
    STATE.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), "event": event, **kw}) + "\n")


def new_draft(kind: str, title: str, body_md: str, provenance: dict, fidelity: dict,
              evidence: str, trigger: dict | None = None) -> dict:
    QUEUE.mkdir(parents=True, exist_ok=True)
    did = dt.datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    d = {"id": did, "created": _now(), "kind": kind, "title": title, "body_md": body_md,
         "provenance": provenance, "fidelity": fidelity, "evidence": evidence,
         "trigger": trigger or {}, "edited": False,
         "status": "pending" if fidelity.get("passed") else "failed_fidelity",
         "review": None}
    (QUEUE / f"{did}.json").write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    log("draft_created", id=did, kind=kind, status=d["status"], study=provenance.get("study_key"))
    return d


def get_draft(did: str) -> dict | None:
    p = QUEUE / f"{did}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_draft(d: dict):
    (QUEUE / f"{d['id']}.json").write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def list_drafts() -> list[dict]:
    if not QUEUE.exists():
        return []
    out = []
    for p in sorted(QUEUE.glob("*.json"), reverse=True):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


OUTBOX = ROOT / "out" / "publish_outbox"


def _copy_charts_to_outbox(d: dict, stem: str) -> list[str]:
    """Copy a draft's attached chart PNGs into the outbox alongside its md/html, so a screenshot-away
    chart still travels with its published bundle. Returns the outbox chart paths."""
    import shutil
    copied = []
    for i, c in enumerate(d.get("charts", []), 1):
        src = Path(c["path"])
        if src.exists():
            dst = OUTBOX / f"{stem}_chart{i}_{src.name}"
            OUTBOX.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            copied.append(str(dst))
    return copied


def attach_charts(did: str, charts: list[dict]) -> dict:
    """Attach chart(s) to a draft. charts: [{template, path, ...structural metadata}]. If the draft is
    ALREADY published, also copy the charts into the outbox now (so an approved piece can gain its chart)."""
    with _LOCK:
        d = get_draft(did)
        if not d:
            raise KeyError(did)
        d["charts"] = charts
        if d.get("status") == "published":
            stem = Path((d.get("review", {}).get("publish", {}) or {}).get("url_or_path", did)).stem or did
            d.setdefault("review", {}).setdefault("publish", {})["charts_outbox"] = \
                _copy_charts_to_outbox(d, stem)
        save_draft(d)
        log("charts_attached", id=did, n=len(charts), status=d.get("status"))
        return d


def approve(did: str, edit_class: str, adapter) -> dict:
    """edit_class: none | taste | correctness. Publishes via the adapter (manual fallback renders for
    paste). Returns the updated draft; raises on ineligible drafts."""
    with _LOCK:
        d = get_draft(did)
        if not d:
            raise KeyError(did)
        if d["status"] not in ("pending",):
            raise ValueError(f"draft is {d['status']}, not approvable")
        if not d["fidelity"].get("passed"):
            raise ValueError("FAILED-FIDELITY drafts cannot be approved — edit until fidelity passes")
        if d["kind"] == "flagship":
            res = adapter.publish_post(d["title"], "measured, not predicted", d["body_md"],
                                       draft_only=(CFG["publisher"].get("post_mode") != "full_publish"))
        else:
            res = adapter.publish_note(d["body_md"])
        d["status"] = "published"
        d["review"] = {"action": "approve", "edit_class": edit_class, "ts": _now(),
                       "publish": dict(res)}
        # chart attachments land in the outbox next to the md/html on approve
        if d.get("charts"):
            stem = Path(str(res.get("url_or_path") or did)).stem or did
            d["review"]["publish"]["charts_outbox"] = _copy_charts_to_outbox(d, stem)
        save_draft(d)
        st = load_state()
        if edit_class == "correctness":
            st["streak"] = 0
        else:
            st["streak"] += 1
        if d["kind"] == "flagship":
            st["last_flagship_ts"] = dt.datetime.now().timestamp()
        sid = f"{'event' if 'event_studies' in d['provenance'].get('artifact','') else 'recovery'}:" \
              f"{d['provenance'].get('study_key')}"
        if sid not in st["published_study_ids"]:
            st["published_study_ids"].append(sid)
        flipped = False
        if (not st["autonomy_enabled"]) and st["streak"] >= CFG["autonomy"]["required_streak"]:
            st["autonomy_enabled"] = True
            flipped = True
        save_state(st)
        log("approved", id=did, edit_class=edit_class, streak=st["streak"],
            publish_mode=res.get("mode"), autonomy_flipped=flipped)
        return d


def reject(did: str, reason: str) -> dict:
    with _LOCK:
        d = get_draft(did)
        if not d:
            raise KeyError(did)
        d["status"] = "rejected"
        d["review"] = {"action": "reject", "reason": reason, "ts": _now()}
        save_draft(d)
        st = load_state()
        st["streak"] = 0
        save_state(st)
        log("rejected", id=did, reason=reason, streak=0)
        return d


def edit(did: str, body_md: str, fidelity_report: dict) -> dict:
    with _LOCK:
        d = get_draft(did)
        if not d:
            raise KeyError(did)
        d["body_md"] = body_md
        d["edited"] = True
        d["fidelity"] = fidelity_report
        if d["status"] in ("pending", "failed_fidelity"):
            d["status"] = "pending" if fidelity_report.get("passed") else "failed_fidelity"
        if body_md.startswith("#"):
            d["title"] = body_md.splitlines()[0].lstrip("# ").strip()
        save_draft(d)
        log("edited", id=did, fidelity_passed=fidelity_report.get("passed"))
        return d


def factual_correction(did: str, note: str) -> dict:
    """TRIPWIRE: a post-publication factual correction auto-reverts the autonomy flag."""
    with _LOCK:
        d = get_draft(did)
        if not d:
            raise KeyError(did)
        d.setdefault("corrections", []).append({"ts": _now(), "note": note})
        save_draft(d)
        st = load_state()
        st["autonomy_enabled"] = False
        st["streak"] = 0
        save_state(st)
        log("factual_correction_tripwire", id=did, note=note, autonomy_enabled=False, streak=0)
        return d
