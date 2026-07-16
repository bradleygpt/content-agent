"""Review-queue server — loopback-only Flask app on 127.0.0.1:8799.

Reached from the phone through markets-llm's EXISTING authenticated tunnel (its server proxies /drafts and
/api/content/* here after enforcing the same bearer-token discipline as /m). Binding loopback means this
server is never directly exposed; the tunnel's auth is the only door.

  .venv/Scripts/python.exe -m content_agent.server
"""
from __future__ import annotations
import json
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from . import queue_store as qs
from .fidelity import run_fidelity
from .publisher import get_adapter

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
app = Flask(__name__)


def _summary(d: dict) -> dict:
    return {"id": d["id"], "created": d["created"], "kind": d["kind"], "title": d["title"],
            "status": d["status"], "edited": d.get("edited", False),
            "fidelity_passed": d["fidelity"].get("passed"),
            "n_failures": len(d["fidelity"].get("failures", [])),
            "n_flags": len(d["fidelity"].get("directional", [])),
            "n_charts": len(d.get("charts", [])),
            "study": d["provenance"].get("study_key"), "trigger": (d.get("trigger") or {}).get("trigger")}


@app.get("/")
def page():
    return send_from_directory(str(ROOT / "content_agent" / "static"), "drafts.html")


@app.get("/api/content/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/content/state")
def state():
    st = qs.load_state()
    return jsonify({"streak": st["streak"], "required_streak": CFG["autonomy"]["required_streak"],
                    "autonomy_enabled": st["autonomy_enabled"],
                    "autonomy_eligible": qs.autonomy_eligible(st),
                    "adapter": get_adapter(CFG).name})


@app.post("/api/content/autonomy/enable")
def autonomy_enable():
    """The explicit confirm of unlock-then-confirm — eligibility never enables autonomy by itself."""
    try:
        st = qs.enable_autonomy()
        return jsonify({"ok": True, "autonomy_enabled": st["autonomy_enabled"], "streak": st["streak"]})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/content/drafts")
def drafts():
    return jsonify({"drafts": [_summary(d) for d in qs.list_drafts()]})


@app.get("/api/content/drafts/<did>")
def draft(did):
    d = qs.get_draft(did)
    return (jsonify(d), 200) if d else (jsonify({"error": "not found"}), 404)


@app.get("/api/content/drafts/<did>/chart/<int:idx>")
def draft_chart(did, idx):
    """Serve an attached chart PNG (deterministic render) for the /drafts thumbnails. Path is validated to
    stay inside the charts dir (no traversal)."""
    from pathlib import Path as _P
    from flask import send_file, abort
    d = qs.get_draft(did)
    charts = (d or {}).get("charts", [])
    if not d or idx < 0 or idx >= len(charts):
        abort(404)
    p = _P(charts[idx]["path"]).resolve()
    charts_root = (ROOT / "out" / "charts").resolve()
    if charts_root not in p.parents or not p.exists():
        abort(404)
    return send_file(str(p), mimetype="image/png")


@app.post("/api/content/drafts/<did>/approve")
def approve(did):
    body = request.get_json(silent=True) or {}
    try:
        d = qs.approve(did, body.get("edit_class", "none"), get_adapter(CFG))
        return jsonify({"ok": True, "status": d["status"], "publish": d["review"]["publish"],
                        "state": qs.load_state()})
    except (KeyError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/content/drafts/<did>/reject")
def reject(did):
    body = request.get_json(silent=True) or {}
    try:
        d = qs.reject(did, body.get("reason", ""), factually_wrong=bool(body.get("factually_wrong")))
        return jsonify({"ok": True, "status": d["status"]})
    except KeyError as e:
        return jsonify({"error": str(e)}), 404


@app.post("/api/content/drafts/<did>/edit")
def edit(did):
    body = request.get_json(silent=True) or {}
    md = (body.get("body_md") or "").strip()
    if not md:
        return jsonify({"error": "empty body"}), 400
    d0 = qs.get_draft(did)
    if not d0:
        return jsonify({"error": "not found"}), 404
    report = run_fidelity(md, d0["evidence"])            # re-run fidelity on the EDITED text pre-publish
    d = qs.edit(did, md, report)
    return jsonify({"ok": True, "status": d["status"], "fidelity": report})


@app.post("/api/content/drafts/<did>/correction")
def correction(did):
    body = request.get_json(silent=True) or {}
    try:
        qs.factual_correction(did, body.get("note", ""))
        return jsonify({"ok": True, "state": qs.load_state()})
    except KeyError as e:
        return jsonify({"error": str(e)}), 404


def main():
    srv = CFG["server"]
    app.run(host=srv["host"], port=srv["port"], debug=False)


if __name__ == "__main__":
    main()
