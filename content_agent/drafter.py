"""Drafting — gemma3:12b via ollama. Two formats: flagship (800-1,200 words) and Notes (single-stat).

THE VOICE (the mission, encoded here): measured evidence in a world of confident noise. Every piece is
built on ONE study the engine actually computed, structured as the weighted two-sided case, every honesty
label carried (SMALL-N, SECTOR-PROXY, CENSORED, INDEX-MEASURED, SURVIVORSHIP, SINGLE-INSTANCE,
DISTRIBUTION). Never makes calls, never predicts, never drops a caveat for punch — the caveats the
incumbent stat-accounts omit ARE the differentiation. Deferral language is the brand.
"""
from __future__ import annotations
import json

import requests

from .studies import CFG

SYSTEM_VOICE = """You are the writing engine for a markets publication whose brand is MEASURED EVIDENCE IN
A WORLD OF CONFIDENT NOISE. Non-negotiable rules:
- Every factual/numeric claim comes ONLY from the MEASURED EVIDENCE block you are given — copy each number
  VERBATIM with its EXACT unit (months stay months, % stays %). Never compute, convert, round differently,
  or introduce a number that is not in the evidence.
- Write numbers as DIGITS exactly as the evidence shows them — "10.2 months", never "ten months"; "-0.9mo"
  may be written "-0.9 months" but never "about a month". Never state a count of recovered/unrecovered/
  failed events unless that exact count appears in the evidence (if it says 0 never recovered, every
  episode recovered — do not invent an exception).
- Carry EVERY honesty label present in the evidence into the piece, by name where natural (SMALL-N,
  SECTOR-PROXY, CENSORED, INDEX-MEASURED, SURVIVORSHIP, SINGLE-INSTANCE, DISTRIBUTION) — the caveats are
  the product, not fine print. Never drop a caveat for punch. The mirror rule is equally hard: NEVER
  assert a label or caveat the evidence does NOT carry — claiming SURVIVORSHIP filtering that never
  happened, or a CENSORED case that doesn't exist, is a false claim exactly like a false number.
- NEVER make a call, prediction, or recommendation. No "expect", no "will", no positioning advice. Close
  with explicit deferral: what the measurement can and cannot say about the future.
- Structure flagship pieces as the weighted two-sided case: what the measured pattern shows, AND the
  honest other side (dispersion, small samples, regime dependence, what would break the pattern).
- If TOPICAL CONTEXT (news headlines) is provided, it may inform WHY this topic is timely — it must NEVER
  be the source of any factual claim. News is framing; measurement is content."""

FLAGSHIP_TASK = """Write a flagship post in GitHub-flavored markdown.
- First line: "# <title>" (a title that signals measurement over folklore, no clickbait).
- 800-1,200 words.
- The spine is the ONE study in the MEASURED EVIDENCE block below. Where the evidence is SMALL-N, present
  EVERY event individually (its own line or bullet with its numbers) — five points is five anecdotes with a
  pattern, not a distribution, and the piece must say so. Where the evidence is a large-N DISTRIBUTION,
  lead with the distribution and use only the evidence's illustrative cases.
- Frame against the folklore version of this topic that confident accounts run (without inventing specific
  claims by others), then show what measurement actually supports.
- SPECIFICALLY FORBIDDEN (these fail the fidelity check): writing an evidence figure as a WORD-NUMBER or a
  rounded form — "ten months", "more than 10 months", "about a month", "one month prior" (when the
  evidence says 10.2mo / 1.5mo) — every evidence figure is quoted as VERBATIM DIGITS with its exact unit
  ("10.2 months", "1.5 months"); DERIVED COUNTS the evidence never prints ("one event did not recover"
  when it says 0 never recovered); and computed spreads or differences between figures — make comparisons
  in WORDS with no number ("the deepest took roughly three times as long") or by quoting both verbatim
  figures side by side.
- Include the weighted two-sided section and a deferral close.
- Output ONLY the markdown post, no preamble, no code fences."""

# For a SECTOR-BY-SECTOR comparative block the unit is SECTORS, not events. The generic FLAGSHIP_TASK's
# "present EVERY event individually" instruction misfires here: there are no per-event-per-sector figures in
# the evidence, so the model fabricates a year-by-year grid (observed 2026-07-14, twice). This task removes
# that instruction and hard-forbids the fabrication.
FLAGSHIP_TASK_COMPARATIVE = """Write a flagship post in GitHub-flavored markdown.
- First line: "# <title>" (a title that signals measurement over folklore, no clickbait).
- 800-1,200 words.
- The spine is the SECTOR-BY-SECTOR comparison in the MEASURED EVIDENCE block. The UNIT IS SECTORS, not
  events. Lead with the ranked per-sector MEDIAN drawdowns, deepest-to-shallowest, and the spread between
  the extremes — the dispersion IS the story.
- HARD CONSTRAINT: the evidence gives ONE median (and one median recovery) PER SECTOR across the events. It
  does NOT give per-event-per-sector figures. DO NOT build a year-by-year or per-event breakdown by sector,
  and DO NOT write any number that is not printed verbatim in the evidence block. If you cannot ground a
  figure, describe the pattern in words instead.
- SPECIFICALLY FORBIDDEN (these fail the fidelity check): computing a SPREAD or DIFFERENCE between two
  figures (e.g. "an 18-point gap" from -27% and -8.9%) — say "the deepest was roughly three times the
  shallowest" in WORDS, or just name the two verbatim figures; and APPROXIMATE numbers ("about 2 months",
  "under 20%", "nearly a fifth") — either quote the exact evidence figure or describe the magnitude with no
  number at all.
- Frame against the folklore ("sector playbook"/"rotation") version confident accounts run, then show what
  the measured dispersion actually supports.
- Give the counterweight FULL editorial weight: SMALL-N (each sector median is over only five events — a
  handful of anecdotes, not a robust ranking) and NOT-A-RANKING (measured PAST dispersion is not a forecast
  or a buy/avoid ranking for the next election) — in your own voice, not as a footnote.
- Include the weighted two-sided section and a deferral close.
- Output ONLY the markdown post, no preamble, no code fences."""

NOTE_TASK = """Write ONE Substack Note (a short single-stat post, 40-130 words, plain text, no markdown
headers). It must contain exactly one measured statistic from the MEASURED EVIDENCE block (copied verbatim
as DIGITS with its unit — never a word-number, never rounded, never "about"/"more than"; comparisons are
made in words without numbers), minimal honest framing, and one deferral sentence. CARRY EVERY honesty label the
evidence block requires, briefly by name — e.g. a Note whose evidence carries SECTOR-PROXY, SINGLE-INSTANCE
and CENSORED might close "(ETF proxy; stress episodes are single instances; one episode still unrecovered)"
— a Note without its labels is not publishable. The mirror rule is equally hard: name ONLY labels the
evidence block actually carries — do not copy label names from this instruction or anywhere else; a caveat
the evidence never stated is a false claim. Output ONLY the note text."""


def _chat(messages: list[dict], num_predict: int) -> str:
    cfg = CFG["drafting"]
    r = requests.post(f"{cfg['ollama_url']}/api/chat",
                      json={"model": cfg["model"], "messages": messages, "stream": False,
                            "options": {"temperature": 0.7, "num_predict": num_predict}},
                      timeout=900)
    r.raise_for_status()
    return (r.json().get("message") or {}).get("content", "").strip()


def draft_flagship(topic: str, evidence: str, news_hints: list[dict] | None = None,
                   fidelity_failures: list[str] | None = None) -> dict:
    user = [f"TOPIC / WHY NOW: {topic}", "", "MEASURED EVIDENCE (the only source of factual claims):",
            evidence]
    if news_hints:
        user += ["", "TOPICAL CONTEXT (framing only — never a source of claims):"]
        user += [f"- {h['headline']}" for h in news_hints[:4]]
    if fidelity_failures:
        user += ["", "FIDELITY FAILURES from your previous attempt — fix EXACTLY these and change nothing "
                     "else about the numbers:"] + [f"- {f}" for f in fidelity_failures]
    # comparative (sector-by-sector) evidence needs the sector-unit task, not the per-event one
    is_comparative = "SECTOR-BY-SECTOR" in evidence or "COMPARATIVE RELATIONAL" in evidence
    user += ["", FLAGSHIP_TASK_COMPARATIVE if is_comparative else FLAGSHIP_TASK]
    body = _chat([{"role": "system", "content": SYSTEM_VOICE},
                  {"role": "user", "content": "\n".join(user)}], num_predict=2400)
    body = body.strip().removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()
    title = body.splitlines()[0].lstrip("# ").strip() if body.startswith("#") else "Untitled"
    return {"kind": "flagship", "title": title, "body_md": body}


def draft_note(evidence: str, stat_focus: str, fidelity_failures: list[str] | None = None) -> dict:
    user = [f"STAT TO FEATURE: {stat_focus}", "",
            "MEASURED EVIDENCE (the only source of factual claims):", evidence]
    if fidelity_failures:
        user += ["", "FIDELITY FAILURES from your previous attempt — fix EXACTLY these:"] + \
                [f"- {f}" for f in fidelity_failures]
    user += ["", NOTE_TASK]
    body = _chat([{"role": "system", "content": SYSTEM_VOICE},
                  {"role": "user", "content": "\n".join(user)}], num_predict=320)
    body = body.strip().strip("`").strip()
    return {"kind": "note", "title": body[:64], "body_md": body}
