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

# THE DAILY MEASURED DIGEST (D1-4). A different contract from the study pieces: the spine is one SESSION,
# not one study, and the failure modes are specific enough to name. The three that this task exists to
# prevent: (a) a median printed alone, which reads as a forecast; (b) a causal sentence connecting the
# context section to the mark, which the evidence never measured; (c) filling a missing section — a
# dispersion-led session genuinely has no conditional distribution, and reaching for one is the lie.
DIGEST_TASK = """Write the daily measured digest in GitHub-flavored markdown.

=== FILL IN THIS SKELETON. Emit these four headings verbatim, in this order, nothing else. ===

# <title: this session and what moved, built from the figures below>

## The mark          (~90 words)
<which anchors crossed and by how much, or — if nothing crossed — the sector spread>

## The context       (~80 words)
<what else moved the same session, as a list of figures. No links between them.>

## Next session      (~200 words)
<the [THE SPINE] horizon in full, per anchor; the [supporting detail] horizons in ONE shared
sentence; the crisis split stated>

## Full recovery     (~180 words)
<time to regain the prior high: median, range, N, the crisis-vs-ordinary contrast, the censored
instance, and the survivorship limitation if the evidence names it>

<close: ~60 words of deferral — what a measured session record can and cannot say about tomorrow>

=== END SKELETON. Total 350-650 words; 650 is a hard ceiling. If a section runs past its budget you
are transcribing the evidence rather than writing — cut. ===

IF THE EVIDENCE HAS NO SECTION 3/4 (no threshold crossing this session): emit ONLY "## The mark" and
"## The context", then the deferral close, and STOP. Do not substitute another study, do not reach for
history that is not in the block, do not pad. A short honest digest is the correct output on a quiet
session.

NOW THE RULES. Every one of these is checked mechanically; a breach fails the draft.

NUMBERS
- Every figure comes from the MEASURED EVIDENCE block, copied VERBATIM as digits with its exact unit.
  Never compute, convert, round, or spell out. Never introduce a number that is not in the evidence.
- A median NEVER appears without its companions IN THE SAME SENTENCE, and which companions depends on
  what it measures:
    * a RETURN median needs its hit rate AND its N: over the next <H> sessions the median was
      <median>%, positive in <hits> of <N> instances (N=<N>);
    * a RECOVERY-TIME median needs its RANGE AND its N: a median of <median> sessions, ranging from
      <min> to <max>, across <N> recovered instances. A duration has NO hit rate — never invent one.
  The angle brackets are PLACEHOLDERS for this session's own figures. Carry no number, ticker or
  phrase out of these instructions into the piece.
- FORBIDDEN: the word "average" in any form, and "mean" as a statistic. Median only. Averaging a
  distribution whose entire content is its spread destroys the thing being reported.

CAUSATION — the single most damaging thing this format can print
- The evidence measures WHAT MOVED, never WHY. You may write that two series moved on the same
  session. You may NOT write that one drove, caused, triggered, explains, reflects or was behind
  another, and you may not imply it with "amid", "as", "after" or "on the back of" used causally, or
  with a "-driven" compound. If you cannot say it without asserting a cause, give the two figures
  side by side and stop.
- THE TITLE IS BOUND BY THIS TOO. A headline that links two moves asserts a cause louder than a
  sentence does. Join the session's figures with a semicolon, not a connective. Write your own title;
  reuse no wording from these instructions.

LABELS
- Carry EVERY label the evidence's "REQUIRED HONESTY LABELS" list names, by name.
- Use ONLY those names. Do not copy label names from these instructions or from pieces you have seen.
  A caveat the evidence never made is a false claim exactly like a false number, and fails just as
  hard. If you believe a limitation exists that the evidence has not named, describe it in plain words
  WITHOUT a label tag.

VOICE
- When two anchors cross, the second must read as prose, not as a refill of the first's template.
  Lead it with what makes it DIFFERENT — a shorter history, a different crisis split, a faster or
  slower recovery — and compare in words. If they are genuinely alike, say so in one sentence.
- "Full recovery" is the payoff, not a footnote: "how long did it take to get back" is the question
  the reader actually has and the number a confident market account never gives them.

Output ONLY the markdown post, no preamble, no code fences."""

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
    """num_ctx MUST be set explicitly. ollama's default is 4096, which counts prompt AND completion —
    so num_predict is a ceiling that the real budget silently undercuts. Measured 2026-07-24: a
    crossing-led digest prompt is 3,402 tokens, leaving 694 for output against a 350-650 word target
    (~500-950 tokens). The first digest truncated mid-sentence with Section 4 missing while
    num_predict=2400 sat unused. Study blocks are ~3x shorter, which is why this surfaced only here."""
    cfg = CFG["drafting"]
    opts = {"temperature": 0.7, "num_predict": num_predict, "num_ctx": cfg.get("num_ctx", 8192)}
    r = requests.post(f"{cfg['ollama_url']}/api/chat",
                      json={"model": cfg["model"], "messages": messages, "stream": False,
                            "options": opts},
                      timeout=900)
    r.raise_for_status()
    body = r.json()
    # a completion that stopped for 'length' is TRUNCATED, not finished — surface it rather than let a
    # half-sentence reach the checker looking like a finished draft.
    if body.get("done_reason") == "length":
        print(f"[drafter] WARNING: generation hit the length ceiling "
              f"(prompt {body.get('prompt_eval_count')} + output {body.get('eval_count')} tokens, "
              f"num_ctx={opts['num_ctx']}) — the draft is truncated")
    return (body.get("message") or {}).get("content", "").strip()


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
    # Task selection follows the EVIDENCE CLASS, not the caller's intent: the block itself says what kind
    # of thing it is, so a mis-routed task can't survive a change of caller.
    if "MEASURED DAILY DIGEST EVIDENCE" in evidence:
        task = DIGEST_TASK
    elif "SECTOR-BY-SECTOR" in evidence or "COMPARATIVE RELATIONAL" in evidence:
        task = FLAGSHIP_TASK_COMPARATIVE
    else:
        task = FLAGSHIP_TASK
    user += ["", task]
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
