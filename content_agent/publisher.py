"""Swappable publisher adapters (C0).

The unofficial cookie-auth Substack API must NEVER be load-bearing: every publish call degrades to the
ManualFallbackAdapter (render final markdown/HTML to out/publish_outbox/ for Bradley to paste). Capability
truth as of C0 (python-substack 0.1.25 source inspection; live validation via scripts/c0_validate.py once
the session cookie exists):

  POSTS — python-substack supports cookie auth (cookies_path/cookies_string), create_draft_from_markdown,
          prepublish_draft, and publish_draft => the full draft-AND-publish path exists in the library.
  NOTES — NEITHER installed library exposes Notes; this adapter implements the raw unofficial endpoint
          (POST https://substack.com/api/v1/comment/feed) with the same session cookie.

Cookie storage (off-repo, like every token in the ecosystem):
  %USERPROFILE%\\.content_agent\\substack_cookies.json   (python-substack export_cookies format), or
  %USERPROFILE%\\.content_agent\\substack_cookie_string.txt  (raw "name=value; ..." from browser devtools)
Re-auth procedure: docs/REAUTH.md.
"""
from __future__ import annotations
import datetime as _dt
import html as _html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTBOX = ROOT / "out" / "publish_outbox"
SECRETS_DIR = Path.home() / ".content_agent"
COOKIES_JSON = SECRETS_DIR / "substack_cookies.json"
COOKIE_STRING = SECRETS_DIR / "substack_cookie_string.txt"


class PublishResult(dict):
    """{ok, mode, detail, url_or_path}"""


def _md_to_html(md: str) -> str:
    """Minimal markdown -> HTML for paste fallback (headers, bold, italics, lists, paragraphs)."""
    out, in_list = [], False
    for line in md.splitlines():
        s = line.rstrip()
        esc = _html.escape(s)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
        esc = re.sub(r"\*(.+?)\*", r"<em>\1</em>", esc)
        if s.startswith("### "):
            out.append(f"<h3>{esc[4:]}</h3>")
        elif s.startswith("## "):
            out.append(f"<h2>{esc[3:]}</h2>")
        elif s.startswith("# "):
            out.append(f"<h1>{esc[2:]}</h1>")
        elif s.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{esc[2:]}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            if s:
                out.append(f"<p>{esc}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _publication() -> tuple[str, str]:
    """(name, url) from config — so the paste-fallback boilerplate carries the real masthead."""
    try:
        cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))["publisher"]
        return cfg.get("publication_name") or "", cfg.get("publication_url") or ""
    except Exception:
        return "", ""


class ManualFallbackAdapter:
    """Always available. Renders the final piece to out/publish_outbox/ for manual paste."""
    name = "manual_fallback"

    def auth_ok(self) -> bool:
        return True

    def publish_post(self, title: str, subtitle: str, markdown: str, draft_only: bool = True):
        stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]
        OUTBOX.mkdir(parents=True, exist_ok=True)
        name, url = _publication()
        byline = f"\n\n---\n*{name} — {url}*\n" if name else ""
        body = f"# {title}\n\n*{subtitle}*\n\n{markdown}{byline}"
        md_path = OUTBOX / f"{stamp}_{slug}.md"
        md_path.write_text(body + "\n", encoding="utf-8")
        (OUTBOX / f"{stamp}_{slug}.html").write_text(_md_to_html(body), encoding="utf-8")
        return PublishResult(ok=True, mode="manual", detail=f"rendered for paste (md + html) for {name}",
                             url_or_path=str(md_path))

    def publish_note(self, text: str):
        stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        OUTBOX.mkdir(parents=True, exist_ok=True)
        p = OUTBOX / f"{stamp}_note.md"
        p.write_text(text + "\n", encoding="utf-8")
        return PublishResult(ok=True, mode="manual", detail="note rendered for paste", url_or_path=str(p))


class SubstackCookieAdapter:
    """Unofficial cookie-auth path. Every method degrades to the manual fallback on ANY failure —
    the unofficial API can break on any Substack change and must never be load-bearing."""
    name = "substack_cookie"

    def __init__(self, publication_url: str | None = None):
        self.publication_url = publication_url
        self.fallback = ManualFallbackAdapter()
        self._api = None

    def _cookie_string(self) -> str | None:
        if COOKIE_STRING.exists():
            return COOKIE_STRING.read_text(encoding="utf-8").strip()
        return None

    def _client(self):
        if self._api is not None:
            return self._api
        from substack import Api
        if COOKIES_JSON.exists():
            self._api = Api(cookies_path=str(COOKIES_JSON), publication_url=self.publication_url)
        elif COOKIE_STRING.exists():
            self._api = Api(cookies_string=self._cookie_string(), publication_url=self.publication_url)
        else:
            raise FileNotFoundError(f"no cookie at {COOKIES_JSON} or {COOKIE_STRING} — see docs/REAUTH.md")
        return self._api

    def auth_ok(self) -> bool:
        try:
            prof = self._client().get_user_profile()
            return bool(prof and (prof.get("id") or prof.get("handle")))
        except Exception:
            return False

    def publish_post(self, title: str, subtitle: str, markdown: str, draft_only: bool = True):
        """draft_only=True (launch default): create the draft; Bradley clicks publish. draft_only=False
        attempts full programmatic publish (library supports it; C0 validates it live)."""
        try:
            api = self._client()
            res = api.create_draft_from_markdown(title=title, markdown=markdown, subtitle=subtitle,
                                                 publish=not draft_only, send=False)
            did = (res or {}).get("id")
            mode = "substack_draft" if draft_only else "substack_published"
            return PublishResult(ok=True, mode=mode, detail=f"draft id {did}", url_or_path=str(did))
        except Exception as e:
            fb = self.fallback.publish_post(title, subtitle, markdown, draft_only)
            fb.update(mode="manual_after_api_failure", detail=f"substack API failed ({e}); {fb['detail']}")
            return fb

    def publish_note(self, text: str):
        """DISABLED 2026-07-14: programmatic Notes posting is what tripped Substack's Spam & Phishing
        detection and got the brand-new account SUSPENDED during C0 validation. This path is hard-gated
        off (config publisher.programmatic_notes_enabled) and falls through to the manual outbox.
        Do not re-enable without an explicit decision — see docs/REAUTH.md.
        Original note (raw unofficial endpoint — no library support exists for Notes (C0 finding)."""
        import json as _json
        try:
            _cfg = _json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
            if not _cfg["publisher"].get("programmatic_notes_enabled", False):
                fb = self.fallback.publish_note(text)
                fb.update(mode="manual_notes_disabled",
                          detail="programmatic Notes DISABLED (account suspension 2026-07-14); " + fb["detail"])
                return fb
        except KeyError:
            pass
        try:
            import requests
            cookie = self._cookie_string()
            if cookie is None and COOKIES_JSON.exists():
                jar = json.loads(COOKIES_JSON.read_text(encoding="utf-8"))
                cookie = "; ".join(f"{c['name']}={c['value']}" for c in jar)
            if not cookie:
                raise FileNotFoundError("no cookie — see docs/REAUTH.md")
            body = {"bodyJson": {"type": "doc", "attrs": {"schemaVersion": "v1"}, "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": text}]}]},
                "tabId": "for-you", "surface": "feed", "replyMinimumRole": "everyone"}
            r = requests.post("https://substack.com/api/v1/comment/feed", json=body,
                              headers={"Cookie": cookie, "Content-Type": "application/json",
                                       "User-Agent": "Mozilla/5.0"}, timeout=30)
            if r.status_code == 200:
                return PublishResult(ok=True, mode="substack_note", detail=f"note id {r.json().get('id')}",
                                     url_or_path="")
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            fb = self.fallback.publish_note(text)
            fb.update(mode="manual_after_api_failure", detail=f"substack API failed ({e}); {fb['detail']}")
            return fb


def get_adapter(cfg: dict):
    """Adapter selection: 'substack' only if a cookie exists; otherwise manual fallback."""
    want = (cfg or {}).get("publisher", {}).get("adapter", "auto")
    have_cookie = COOKIES_JSON.exists() or COOKIE_STRING.exists()
    if want == "manual" or (want == "auto" and not have_cookie):
        return ManualFallbackAdapter()
    return SubstackCookieAdapter((cfg or {}).get("publisher", {}).get("publication_url"))
