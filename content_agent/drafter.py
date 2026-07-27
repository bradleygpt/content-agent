"""Drafting — gemma3:12b via ollama. Two formats: flagship (800-1,200 words) and Notes (single-stat).

THE VOICE (the mission, encoded here): measured evidence in a world of confident noise. Every piece is
built on ONE study the engine actually computed, structured as the weighted two-sided case, every honesty
label carried (SMALL-N, SECTOR-PROXY, CENSORED, INDEX-MEASURED, SURVIVORSHIP, SINGLE-INSTANCE,
DISTRIBUTION). Never makes calls, never predicts, never drops a caveat for punch — the caveats the
incumbent stat-accounts omit ARE the differentiation. Deferral language is the brand.
"""
from __future__ import annotations
import json
import re

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

# THE MEASURED RELATIONSHIP piece (relational content rebuild, item 3). The evidence class is a PAIR
# with per-regime rows: one overall correlation, five episode fingerprints (each SINGLE-INSTANCE), and
# a walk-forward persistence line. The piece's shape is "how X and Y actually move together, and when
# that broke" — the regime where the number diverged from the overall IS the story. The two failure
# modes this task exists to prevent: (a) narrating a correlation as a mechanism ("stocks fell BECAUSE
# yields rose" — the evidence measures co-movement, never cause, and the causal check fails it);
# (b) presenting an episode fingerprint as a distribution — every per-regime number is one historical
# instance of that regime type, and the piece must say so.
PAIR_TASK = """Write a flagship post in GitHub-flavored markdown about ONE measured relationship.
- First line: "# <title>" (a title that signals measurement over folklore, no clickbait; name the two
  series, not a story about them).
- 500-900 words.
- The spine is the relationship in the MEASURED RELATIONAL EVIDENCE block: how the two series actually
  moved together, regime by regime. Open with the overall (full-period) correlation and what a single
  full-period number hides; then walk the per-regime fingerprint; give the greatest editorial weight to
  the episode where the relationship BROKE from its overall pattern — that divergence is the piece.
- Every correlation is quoted as VERBATIM DIGITS ("0.3307", "-0.0977"), never rounded, never as a
  word ("weakly positive" may DESCRIBE a quoted figure, never replace it). Episode day-counts (n=)
  quote verbatim too.
- Every per-regime number is a SINGLE INSTANCE — one 2008, one 2020, one 2022 — not a distribution.
  Say so in your own voice, and carry every label the evidence's REQUIRED HONESTY LABELS list names.
- CO-MOVEMENT IS NOT CAUSE. Never write that one series drove, led, caused, responded to, or moved
  because of the other — the evidence contains correlations, and a correlation has no direction. If
  the evidence carries a sign-flip NOTE (yield-vs-price), state it in your own words; the reader must
  not be left to flip the sign themselves.
- Persistence: report the walk-forward sign-agreement and drift verbatim, and say in plain words
  whether that makes the relationship durable or regime-contingent — using the evidence's own framing,
  not a stronger one.
- Include the weighted two-sided section and a deferral close: what a measured co-movement record can
  and cannot say about the next regime.
- Output ONLY the markdown post, no preamble, no code fences."""

# THE DAILY MEASURED DIGEST (D1-4). A different contract from the study pieces: the spine is one SESSION,
# not one study, and the failure modes are specific enough to name. The three that this task exists to
# prevent: (a) a median printed alone, which reads as a forecast; (b) a causal sentence connecting the
# context section to the mark, which the evidence never measured; (c) filling a missing section — a
# dispersion-led session genuinely has no conditional distribution, and reaching for one is the lie.
DIGEST_TASK = """Write the daily measured digest in GitHub-flavored markdown.

=== FILL IN THIS SKELETON. Emit these five headings verbatim, in this order, nothing else. ===

# <title: this session and what moved, from THIS session's figures. NO causal connective —
#  no amid / as / after / on / driven by / despite / on the back of. Join with a semicolon.
#  Write your own; copy no wording from these instructions.>

## The mark          (~90 words)
<which anchors crossed and by how much, or — if nothing crossed — the sector spread>

## The context       (~80 words)
<what else moved the same session, as a list of figures. No links between them.>

## Similar sessions  (~120 words)
<the nearest analog sessions by measured state: name 2-4 of the dated sessions EXACTLY as the
evidence writes them (YYYY-MM-DD), each with its own next-5 and next-20 outcome; the year
composition in one or two sentences; then, only if the evidence carries one, the 5-session
aggregate in ONE sentence with its hit rate and N. It is secondary — the named sessions lead.>

## Next session      (~200 words)
<the horizon the evidence marks as THE PIECE'S ANSWER, in full, per anchor; the longer-arc
horizon after it with its own hit rate and N; the supporting horizon in one brief sentence;
the crisis split stated>

## Full recovery     (~180 words)
<time to regain the prior high: median, range, N, the crisis-vs-ordinary contrast, the censored
instance, and the survivorship limitation if the evidence names it>

<close: ~60 words of deferral — what a measured session record can and cannot say about tomorrow>

=== END SKELETON. Total 400-800 words; 800 is a hard ceiling. If a section runs past its budget you
are transcribing the evidence rather than writing — cut. ===

IF THE EVIDENCE HAS NO SECTION 3/4 (no threshold crossing this session): emit ONLY "## The mark",
"## The context" and "## Similar sessions", then the deferral close, and STOP. Do not substitute
another study, do not reach for history that is not in the block, do not pad. A short honest digest
is the correct output on a quiet session. If the evidence also has no SECTION 2A, omit "## Similar
sessions" too — never write a section whose evidence is absent.

SIMILAR SESSIONS — the rules specific to that section
- Analog dates are DATA. Cite them exactly as the evidence writes them (YYYY-MM-DD). A date the
  evidence does not contain is a fabricated fact and fails the draft.
- NEVER state a count of the analog sessions you chose to name ("the five sessions", "fifteen
  analogs") — that number is yours, not the evidence's, and it fails the draft. The only set sizes
  that exist are the ones the evidence prints (the analog count and the eligible pool); use those
  verbatim or no count at all. The instances have their own counts; sessions and instances are
  different units — copy each with the unit the evidence gives it.
- Each analog's outcomes belong to that dated session alone. NEVER combine the analogs' 20-session
  outcomes into a median, average, tendency, or lean — the evidence deliberately carries none, and
  inventing one is inventing a number.
- Similarity is measured on state variables, not on stories. Do not write that this session
  "echoes", "mirrors" or "repeats" a named year or crisis — say which dated sessions the state most
  resembles and what each did, then stop.

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
- NEVER REPRODUCE THE EVIDENCE BLOCK'S INSTRUCTION TEXT. The block tells you what to do in imperative
  language ("do not write that one caused...", "state this", "never impute it", "lead with the range").
  That wording is a CONSTRAINT ON YOUR WRITING, not content to publish. A reader who opens the piece and
  finds raw instruction text pasted into a paragraph — or a bracketed block of label text — is worse
  served than by the error the instruction was preventing. Name the label, then state the caveat IN YOUR
  OWN WORDS, in a normal sentence. Never paste a bracketed [LABEL: ...] block into the prose.
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

# THE QUIET-SESSION DIGEST (scope doc SCOPE_quiet_shape_drafting.md, option (a)).
# A/B RESULT 2026-07-27: DID NOT CLEAR (2/4 at t0.7, 1/4 at t0.4, bar >=3/4) — NOT ROUTED.
# Kept because the measurement is the artifact: vs the full task's 0/8 baseline on identical frozen
# evidence, failures collapsed from 8-20 per draft to 0-4 and word counts landed in budget, so the
# word-budget-as-invention-pressure hypothesis is confirmed even though the bar wasn't met. Feeds
# the option-(b) decision (quiet sessions as notes), which is Bradley's product call.
# A dispersion-led session carries ~300 words of actual evidence; the full skeleton's 400-800-word
# expectation is the invention pressure (measured 2026-07-27: 0-for-8 attempts, failures all padding —
# fabricated sections, habit labels, verbalised numbers). This variant is SHORTER THAN THE EVIDENCE
# FEELS, on purpose: three headings, a hard 400-word ceiling, and an explicit license to stop.
DIGEST_TASK_QUIET = """Write the daily measured digest for a QUIET session in GitHub-flavored markdown.

=== FILL IN THIS SKELETON. Emit these three headings verbatim, in this order, NOTHING ELSE.
There is no "Next session" and no "Full recovery" today — no anchor crossed a threshold, so no
conditional distribution and no recovery measurement exists. Writing those headings fails the draft. ===

# <title: this session's spread, from THIS session's figures. NO causal connective — no amid / as /
#  after / driven by / despite. Join with a semicolon. Write your own; copy no wording from here.>

## The mark          (~60 words)
<the best-to-worst sector spread and its two named legs — that IS today's story>

## The context       (~50 words)
<what else moved the same session, as a short list of figures. No links between them.>

## Similar sessions  (~110 words)
<name 2-3 analog dates EXACTLY as the evidence writes them (YYYY-MM-DD), each with its own
next-5 and next-20 outcome; the year composition in one sentence; the 5-session aggregate (only
if the evidence carries one) in ONE sentence with its hit rate and N>

<close: ~40 words of deferral — what a measured quiet session can and cannot say about tomorrow>

=== END SKELETON. Total 220-320 words; 400 is a HARD ceiling. A quiet session's digest is SUPPOSED
to be short — the honest output is a small one, and padding past the evidence is how false claims
happen. When you have stated the spread, the context figures and the analogs, STOP. ===

THE RULES — every one checked mechanically; a breach fails the draft.
- Every figure comes from the MEASURED EVIDENCE block, copied VERBATIM as digits with its exact
  unit. Never compute, convert, round, or spell out a number — "twenty" and "fifteen" are failures;
  write the evidence's digits or no count at all. Never introduce a number not in the evidence.
- Analog dates are DATA: cite them exactly (YYYY-MM-DD). A date not in the evidence fails the draft.
- NEVER combine the analogs' 20-session outcomes into a median, average, tendency or lean — the
  evidence deliberately carries none. A median, where you state one, carries its hit rate and N in
  the same sentence. The word "average" and "mean" as a statistic are forbidden.
- NO CAUSATION anywhere, title included: nothing drove, caused, triggered, explains or was behind
  anything — the evidence measures what moved, never why.
- Carry EVERY label the evidence's REQUIRED HONESTY LABELS list names, in your own words; assert
  NONE it does not name. On a quiet session there is usually no CENSORED and no SURVIVORSHIP — do
  not import them from habit.
Output ONLY the markdown post, no preamble, no code fences."""

# THE QUIET-SESSION DIGEST NOTE (option (b) ADOPTED 2026-07-27). The daily identity is now:
# flagship when the market moved (a crossing), note when it didn't (dispersion-led). The note form
# is the EXISTENCE-PROVEN shape for thin evidence — the nightly's unattended pair notes went 2-for-3
# on first exposure while two shortened-flagship arms failed their A/B on the same quiet evidence.
# This is a proper note task for the digest evidence class, not a truncated flagship.
DIGEST_NOTE_TASK = """Write ONE short daily note for a QUIET session (no threshold crossing):
40-130 words, plain text, no markdown headers. In order:
  (1) the session's best-to-worst sector spread with its two named legs — figures VERBATIM as
      digits with their units;
  (2) the S&P 500 reference move, WITH a brief in-your-own-words index caveat (an index or
      sector-ETF figure is shallower than a typical single stock's) — this sentence is mandatory,
      not optional colour;
  (3) ONE sentence on the similar-sessions composition: name ONLY years the evidence's year
      composition actually lists (years only is fine; any count you give is verbatim digits), or
      cite 1-2 analog dates EXACTLY as written (YYYY-MM-DD). The eligible pool is counted in
      SESSIONS — if you state it, write "sessions", never "days";
  (4) one deferral sentence.
RULES (checked mechanically): every figure verbatim from the MEASURED EVIDENCE block — never
computed, rounded, or spelled out ("twenty" is a failure; write the digits or no number). Never
combine the analogs' outcomes into a median, average, tendency or lean the evidence does not print;
a median you do state carries its hit rate and N in the same sentence. NO causal language — nothing
drove, caused, triggered or explains anything. Carry EVERY label the evidence's REQUIRED HONESTY
LABELS list names, briefly in your own words; assert NONE it does not name (no CENSORED or
SURVIVORSHIP from habit — a quiet session usually has neither). Output ONLY the note text."""

NOTE_TASK = """Write ONE Substack Note (a short single-stat post, 40-130 words, plain text, no markdown
headers). It must contain exactly one measured statistic from the MEASURED EVIDENCE block (copied verbatim
as DIGITS with its unit — never a word-number, never rounded, never "about"/"more than"; comparisons are
made in words without numbers), minimal honest framing, and one deferral sentence. CARRY EVERY honesty label the
evidence block requires, briefly by name — e.g. a Note whose evidence carries SECTOR-PROXY, SINGLE-INSTANCE
and CENSORED might close "(ETF proxy; stress episodes are single instances; one episode still unrecovered)"
— a Note without its labels is not publishable. The mirror rule is equally hard: name ONLY labels the
evidence block actually carries — do not copy label names from this instruction or anywhere else; a caveat
the evidence never stated is a false claim. Output ONLY the note text."""


# ======================================================================================================
# DETERMINISTIC POST-PROCESSING — two defects the prompt could not fix in three attempts each.
#
# Both are MECHANICAL and both are LOGGED: the returned change list rides into the draft record so a
# reviewer sees exactly what was rewritten and can disagree. Neither touches a number, a label or a
# claim — one rewrites a connective in the title, the other inserts a heading the model omitted. Chosen
# over regenerate-on-precheck because a regeneration costs a GPU cycle to fix a comma.
# ======================================================================================================
_TITLE_CAUSAL_RX = re.compile(
    r"\s+(?:amid(?:st)?|as|after|despite|following|on\s+the\s+back\s+of|driven\s+by|due\s+to|"
    r"amidst|owing\s+to|thanks\s+to|because\s+of)\s+", re.I)
_DIGEST_HEADINGS = ["The mark", "The context", "Similar sessions", "Next session", "Full recovery"]


def _strip_recited_sentences(body: str, evidence: str) -> tuple[str, list[str]]:
    """Remove whole sentences that recite the evidence's INSTRUCTION text verbatim.

    Fourth occurrence across four rounds, so the prompt is not the lever. Deliberately conservative:
    a sentence is dropped ONLY when >= 9 of its consecutive words appear verbatim in an evidence line
    that is imperative. Quoting FIGURES is the job and is never an instruction line, so a numbers
    sentence can never be removed; and removing a whole sentence leaves the surrounding prose intact
    where removing a fragment would not."""
    # AN EVIDENCE LINE CARRYING DIGITS IS DATA, NOT INSTRUCTION — even when it also contains a
    # directive. The spine line reads "over the next 20 sessions ... lead with it: median 2.52%,
    # positive in 158 of 262 instances", so matching on "lead with" alone classified the piece's
    # PRIMARY FIGURES as instruction text and this function deleted the draft's 20-session paragraph.
    # The draft then PASSED fidelity, because everything that survived still bound — a content-deleted
    # draft sitting in the queue looking publishable, which is worse than any failure. Pure directives
    # (INDEX-MEASURED, SECTOR-PROXY, NO CAUSATION) carry no digits; data lines always do.
    instr = [ln for ln in evidence.splitlines()
             if re.search(r"\bdo not\b|\bnever\b|\bsay so\b|\bstate this\b|\bin your own words\b|"
                          r"\bapplies here\b|\bforbidden\b|\bomit\b|\btell the reader\b", ln, re.I)
             and not re.search(r"\d", ln)]
    if not instr:
        return body, []

    def words(s):
        return re.sub(r"[^0-9a-z ]+", " ", s.lower()).split()

    instr_join = " | ".join(" ".join(words(ln)) for ln in instr)
    kept, dropped = [], []
    for para in body.split("\n"):
        sents, out = re.split(r"(?<=[.!?])\s+", para), []
        for s in sents:
            w = words(s)
            recited = any(" ".join(w[i:i + 9]) in instr_join for i in range(0, max(0, len(w) - 9) + 1)) \
                if len(w) >= 9 else False
            if recited:
                dropped.append(s.strip()[:90])
            else:
                out.append(s)
        # ALWAYS rebuild from the kept sentences. The earlier "if len(sents) > 1 else para" fallback
        # silently discarded the filtering whenever a paragraph held a single sentence — which is
        # exactly the shape a pasted label block takes.
        kept.append(" ".join(x for x in out if x.strip()))
    changes = ([f"removed {len(dropped)} sentence(s) reciting the evidence's instruction text "
                f"(first: {dropped[0]!r})"] if dropped else [])
    return ("\n".join(kept), changes) if dropped else (body, [])


def normalize_digest_markdown(body: str, evidence: str = "") -> tuple[str, list[str]]:
    """-> (body, changes). Deterministic repairs for the digest format only.

    1. TITLE CONNECTIVE -> SEMICOLON. Three prompt attempts failed to stop "X Declines Amid Y"; a
       headline linking two moves asserts a cause the evidence never measured. The connective becomes
       "; ", which is the house form the task asks for anyway. Numbers and names are untouched.
    2. MISSING FIRST HEADING. The model reliably writes the mark content directly under the title and
       heads only the later sections (0/4, then 2/4, then 3/4 across three rounds). When "## The
       context" exists but "## The mark" does not, and there IS prose between the title and it, that
       prose IS the mark section — so the heading is inserted rather than requested again.
    """
    changes, lines = [], body.splitlines()
    if not lines:
        return body, changes

    for i, ln in enumerate(lines[:3]):
        if ln.lstrip().startswith("#") and _TITLE_CAUSAL_RX.search(ln):
            new = _TITLE_CAUSAL_RX.sub("; ", ln, count=1).rstrip("; ")
            changes.append(f"title: causal connective replaced with a semicolon "
                           f"({ln.strip()[:70]!r} -> {new.strip()[:70]!r})")
            lines[i] = new
            break

    # 3. RECITED INSTRUCTION SENTENCES ARE DROPPED — before the heading pass, so a paragraph that was
    #    ONLY a recited sentence is empty by the time headings are inserted.
    text, rec = _strip_recited_sentences("\n".join(lines), evidence)
    changes += rec
    lines = text.splitlines()

    has = {h: re.search(rf"(?mi)^\s{{0,3}}#{{1,4}}\s*{re.escape(h)}\b", text) for h in _DIGEST_HEADINGS}
    if not has["The mark"] and has["The context"]:
        h1 = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith("# ")), None)
        ctx = next(i for i, ln in enumerate(lines)
                   if re.match(r"(?i)^\s{0,3}#{1,4}\s*The context\b", ln))
        first = next((i for i in range((h1 + 1) if h1 is not None else 0, ctx) if lines[i].strip()), None)
        if first is not None:
            lines.insert(first, "## The mark")
            lines.insert(first, "")
            changes.append('inserted the omitted "## The mark" heading above the mark prose')
            text = "\n".join(lines)
    return text, changes


def _chat(messages: list[dict], num_predict: int) -> str:
    """num_ctx MUST be set explicitly. ollama's default is 4096, which counts prompt AND completion —
    so num_predict is a ceiling that the real budget silently undercuts. Measured 2026-07-24: a
    crossing-led digest prompt is 3,402 tokens, leaving 694 for output against a 350-650 word target
    (~500-950 tokens). The first digest truncated mid-sentence with Section 4 missing while
    num_predict=2400 sat unused. Study blocks are ~3x shorter, which is why this surfaced only here."""
    cfg = CFG["drafting"]
    # temperature is config-exposed (default unchanged at 0.7) so the quiet-shape A/B — and any
    # future per-shape tuning that clears its own measurement — has a lever that is data, not code.
    opts = {"temperature": cfg.get("temperature", 0.7), "num_predict": num_predict,
            "num_ctx": cfg.get("num_ctx", 8192)}
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
        # QUIET-SHAPE ROUTING REMOVED: the A/B against the frozen 07-27 evidence did not clear its
        # pre-registered bar (A1 short-task/t0.7: 2/4; A2 short-task/t0.4: 1/4; bar >=3/4; baseline
        # 0/8). DIGEST_TASK_QUIET stays in the file as the measured artifact for the option-(b)
        # product decision — do not re-route to it without a new cleared measurement.
        task = DIGEST_TASK
    elif "SECTOR-BY-SECTOR" in evidence or "COMPARATIVE RELATIONAL" in evidence:
        task = FLAGSHIP_TASK_COMPARATIVE
    elif "MEASURED RELATIONAL EVIDENCE" in evidence:
        # the single-pair relationship block (comparative already matched above, so this cannot
        # swallow the multi-pair class whose header contains the same three words)
        task = PAIR_TASK
    else:
        task = FLAGSHIP_TASK
    user += ["", task]
    body = _chat([{"role": "system", "content": SYSTEM_VOICE},
                  {"role": "user", "content": "\n".join(user)}], num_predict=2400)
    body = body.strip().removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()
    normalised = []
    if "MEASURED DAILY DIGEST EVIDENCE" in evidence:
        body, normalised = normalize_digest_markdown(body, evidence)
        for c in normalised:
            print(f"[drafter] normalised -> {c}")
    title = body.splitlines()[0].lstrip("# ").strip() if body.startswith("#") else "Untitled"
    return {"kind": "flagship", "title": title, "body_md": body, "normalised": normalised}


def draft_note(evidence: str, stat_focus: str, fidelity_failures: list[str] | None = None) -> dict:
    user = [f"STAT TO FEATURE: {stat_focus}", "",
            "MEASURED EVIDENCE (the only source of factual claims):", evidence]
    if fidelity_failures:
        user += ["", "FIDELITY FAILURES from your previous attempt — fix EXACTLY these:"] + \
                [f"- {f}" for f in fidelity_failures]
    # task selection follows the EVIDENCE CLASS, same law as draft_flagship: digest-class evidence
    # gets the quiet-session digest note, everything else the generic single-stat note.
    task = DIGEST_NOTE_TASK if "MEASURED DAILY DIGEST EVIDENCE" in evidence else NOTE_TASK
    user += ["", task]
    body = _chat([{"role": "system", "content": SYSTEM_VOICE},
                  {"role": "user", "content": "\n".join(user)}], num_predict=320)
    body = body.strip().strip("`").strip()
    return {"kind": "note", "title": body[:64], "body_md": body}
