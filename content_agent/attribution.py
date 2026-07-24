"""PRIMARY-SOURCE ATTRIBUTION — CITED ONLY, NEVER AUTHORED (Daily Digest D1-5).

The digest reports what moved. It must never explain WHY, because the engine measures no such thing. The
single exception is a primary-source document that exists in the window: an SEC filing or a Fed release.
Those are reproduced VERBATIM — headline, source, date, link — and nothing else happens to them.

THE HARD RULES, enforced structurally rather than by instruction:

  1. NO MODEL. Nothing in this module calls an LLM. Headlines are copied byte-for-byte from the feed;
     `verbatim=True` on every record is the claim that they were not touched.
  2. NO SUMMARISATION, NO INTERPRETATION. A filing title is reproduced or omitted. There is no path that
     shortens, paraphrases, or characterises one.
  3. NO CAUSAL LINKAGE. A citation is attached to a ticker because the filing IS that issuer's, never
     because it "explains" the move. The evidence block says this to the drafter in as many words, and
     the co-occurrence is described as timing, not cause.
  4. SILENCE OVER INVENTION. No filing in the window -> the section is omitted. The cross-asset context
     carries the post. An empty result is a correct result.

Sources are primary only, and both are public, free, and documented for automated access:
  - SEC EDGAR full-text company feed (an 8-K is the "something happened" filing).
    Fair-access rules require a declared User-Agent and <=10 req/s; this stays far under both.
  - Federal Reserve press-release RSS.
Secondary-source news integration is DEFERRED by scope decision — a secondary headline is someone's
interpretation, and reproducing it verbatim launders that interpretation into the digest.
"""
from __future__ import annotations

import datetime as dt
import re
import urllib.request
import xml.etree.ElementTree as ET

from .studies import CFG

# SEC fair-access: a descriptive User-Agent with a contact is REQUIRED, not optional.
_UA = CFG.get("sec_user_agent", "markets-llm digest (contact: bmhartnett1990@gmail.com)")
_EDGAR_CIK = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K&dateb=&owner=include&count=10&output=atom"
_FED_RSS = "https://www.federalreserve.gov/feeds/press_all.xml"
_TIMEOUT = 20


def _get(url: str) -> bytes | None:
    """Fetch, or return None. A failed citation lookup NEVER breaks a digest — the section is simply
    omitted, which is the honest outcome of "no primary source found"."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Encoding": "gzip, deflate"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        return raw
    except Exception:
        return None


def _in_window(date_str: str, as_of: str, days: int) -> bool:
    try:
        d = dt.date.fromisoformat(date_str[:10])
    except ValueError:
        return False
    ref = dt.date.fromisoformat(as_of[:10])
    return 0 <= (ref - d).days <= days


def fed_releases(as_of: str, window_days: int = 1) -> list[dict]:
    """Fed press releases in the window, VERBATIM. Title copied exactly; never condensed."""
    raw = _get(_FED_RSS)
    if not raw:
        return []
    out = []
    try:
        root = ET.fromstring(raw)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            iso = _rfc822_to_iso(pub)
            if not (title and iso and _in_window(iso, as_of, window_days)):
                continue
            out.append({"ticker": "—", "headline": title, "source": "Federal Reserve press release",
                        "date": iso, "url": link, "verbatim": True})
    except ET.ParseError:
        return []
    return out


def _rfc822_to_iso(s: str) -> str | None:
    m = re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", s)
    if not m:
        return None
    months = {m_: i + 1 for i, m_ in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
    mo = months.get(m.group(2))
    return f"{m.group(3)}-{mo:02d}-{int(m.group(1)):02d}" if mo else None


def issuer_8k(cik: str, ticker: str, as_of: str, window_days: int = 1) -> list[dict]:
    """8-K filings by ONE issuer in the window, VERBATIM. Attached because the filing IS this issuer's —
    never because it is claimed to explain a price move."""
    raw = _get(_EDGAR_CIK.format(cik=cik))
    if not raw:
        return []
    out = []
    try:
        root = ET.fromstring(raw)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//a:entry", ns):
            title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
            updated = (entry.findtext("a:updated", default="", namespaces=ns) or "").strip()
            link_el = entry.find("a:link", ns)
            link = link_el.get("href") if link_el is not None else ""
            if not (title and updated and _in_window(updated, as_of, window_days)):
                continue
            out.append({"ticker": ticker, "headline": title, "source": "SEC EDGAR 8-K",
                        "date": updated[:10], "url": link, "verbatim": True})
    except ET.ParseError:
        return []
    return out


def citations_for(as_of: str, ciks: dict[str, str] | None = None, window_days: int = 1) -> list[dict]:
    """All primary-source citations for the session. Empty list is a normal, correct outcome —
    the caller omits the section rather than reaching for a secondary source."""
    out = list(fed_releases(as_of, window_days))
    for ticker, cik in (ciks or CFG.get("digest_ciks", {})).items():
        out.extend(issuer_8k(cik, ticker, as_of, window_days))
    return out


def assert_verbatim(citations: list[dict], feed_titles: set[str]) -> list[str]:
    """Guard: every cited headline must appear EXACTLY in what the feed served. Any citation whose text
    is not byte-identical to a served title is rejected — the structural check that no summarisation,
    truncation, or 'tidying' ever slipped in between fetch and render."""
    return [c["headline"] for c in citations if c["headline"] not in feed_titles]
