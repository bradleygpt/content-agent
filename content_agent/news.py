"""News layer — TOPICALITY ONLY, never claims. Zero-cost RSS.

Headlines may surface which study is topical this week ("semis sold off" -> the SMH recovery study); the
draft's factual claims come ONLY from engine evidence. That separation is enforced in the drafting prompt
(news text is passed as FRAMING CONTEXT with an explicit no-claims instruction) and backstopped by the
fidelity checker (a number sourced from a headline has no evidence match and hard-fails).
"""
from __future__ import annotations
import re

from .studies import CFG

_TOPIC_MAP = [
    (r"semiconductor|chipmaker|chip stocks|nvidia|micron|amd\b|tsmc", "recovery:ANCHOR_SMH"),
    (r"\bfed\b|fomc|powell|rate (cut|hike|decision)|federal reserve", "event:fomc_meeting"),
    (r"midterm", "event:midterm_election"),
    (r"presidential election|white house race", "event:pres_election"),
    (r"bank stocks|banking sector|financials", "recovery:ANCHOR_XLF"),
    (r"\bgold\b", "recovery:ANCHOR_GOLD"),
    (r"\boil\b|crude", "recovery:ANCHOR_OIL_WTI"),
    (r"selloff|sell-off|correction|drawdown|bear market", "recovery:ANCHOR_SPY"),
]


def topical_hints(max_per_feed: int = 12) -> list[dict]:
    """-> [{headline, feed, study_id}] for headlines matching a mapped study. Failures are silent —
    news is a nice-to-have; the pipeline never depends on it."""
    try:
        import feedparser
    except ImportError:
        return []
    hints = []
    for url in CFG.get("news_feeds", []):
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                title = getattr(entry, "title", "") or ""
                low = title.lower()
                for pat, sid in _TOPIC_MAP:
                    if re.search(pat, low):
                        hints.append({"headline": title.strip(), "feed": url, "study_id": sid})
                        break
        except Exception:
            continue
    return hints
