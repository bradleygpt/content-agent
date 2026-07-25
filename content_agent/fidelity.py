"""THE FIDELITY CHECKER — deterministic hard precondition; no draft reaches the queue without it.

1. NUMERIC BINDING: every numeric token in the draft must match a number in the cited evidence INCLUDING
   ITS UNIT. "2.5 months" in evidence vs "2.5 weeks" in draft is a HARD FAIL (the twice-observed bug this
   module exists to kill). Normalization is trivial-formatting only: unicode minus, %/percent, word numbers
   ("six weeks"), hyphenated units ("3.6-month"). Nothing looser. A draft number with no evidence match at
   all is also a hard fail.
2. LABEL COMPLETENESS + LEGITIMACY: every honesty label present in the source evidence block must appear
   in the draft; and a label the draft ASSERTS that the evidence never carries is a hard fail
   (INVENTED-LABEL) — a false caveat damages the brand exactly as a false number does (observed
   2026-07-13: SURVIVORSHIP claimed on a study where all five events were included).
3. DIRECTIONAL-CLAIM FLAGGING: sentences combining engine attribution with directional verbs are flagged
   with their numeric-bind status for the reviewer (visible, not auto-failed — the "upward drift after
   FOMC" embellishment class is not fully decidable deterministically). A number-free directional sentence
   is flagged only when an ADJACENT sentence makes an engine-attributed numeric claim; number-free
   narrative framing with number-free neighbors is editorial voice, not a checkable claim.

Draft-side unit detection is NARROW (nearest unit word within ~25 chars — the draft must state its unit
adjacently); evidence-side is CLAUSE-WIDE (to end of clause), so "recovery median 3.6, range 0.5..14.0
months" indexes all three values as months. A unitful draft value found in evidence only under a DIFFERENT
unit reports UNIT-MISMATCH explicitly.
"""
from __future__ import annotations
import re

# NAMES/IDIOMS CONTAINING DIGITS THAT ARE NOT DATA (stripped before extraction, both sides).
#
# THE AUDIT THAT BELONGS WITH THIS LIST: adding a series to the digest universe means checking whether
# its LABEL carries a digit. "Nikkei 225" reached production unstripped, so "the Nikkei 225 in Japan
# lower by -2.73%" parsed 225 as a percentage and hard-failed — the fourth instance of introducing
# something without extending the checker (after "sessions", the ^TNX scale, and "pp"). The earlier
# notation audit checked UNIT TOKENS only, so a name with a digit walked straight through it. The
# self-test now enumerates BOTH: every unit notation AND every digit-bearing name the digest can print.
_STRIP_PATTERNS = [r"s\s*&\s*p\s*500", r"sp500", r"s&p500", r"nasdaq[\s-]?100", r"russell[\s-]?2000",
                   # digest context series whose LABELS carry digits (found by enumerating the label
                   # set, not by waiting for each to fail): Nikkei 225, EURO STOXX 50, and the US
                   # 10-year Treasury. The last is scoped to the instrument phrase, NOT bare
                   # "10-year", so a genuine "10-year recovery" elsewhere still measures.
                   r"nikkei[\s-]?225", r"euro\s*stoxx\s*50", r"\b(?:us\s+)?10-?year\s+treasury\b",
                   r"\b10-?k\b", r"\b10-?q\b", r"\b2s10s\b", r"\b10y\b", r"\bcovid-19\b", r"\b60/40\b",
                   r"\b24/7\b", r"\b401\(k\)\b"]
_WORD_NUMS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
              "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
              "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20}
_UNIT_RX = [
    ("pct", r"%|percent(?:age)?(?:\s+points?)?|per\s+cent|\bpps?\b|\bbps\b"),
    ("month", r"months?\b|mo\b"),
    ("week", r"weeks?\b|wks?\b"),
    ("day", r"days?\b"),
    ("year", r"years?\b|yrs?\b"),
    # "session" is its OWN unit, deliberately NOT folded into count. A trading session is not a calendar
    # day: "542 sessions" is ~2.2 years, "542 days" is ~1.5. Keeping them distinct means a draft that
    # writes days where the evidence says sessions still hard-fails, which is the whole point of unit
    # binding. (The digest denominates both its horizons and its recovery times in sessions, so the
    # lexicon has to know the word — without it, "over the next 20 sessions was 1.73%" resolved 20 to
    # PCT from the trailing figure and failed every digest that stated a horizon in prose.)
    ("session", r"sessions?\b"),
    ("count", r"events?\b|meetings?\b|midterms?\b|elections?\b|episodes?\b|cases?\b|instances?\b|"
              r"drawdowns?\b|anecdotes?\b|stocks?\b|names?\b|(?:data\s+)?points?\b|occurrences?\b|"
              r"cycles?\b|samples?\b|\bN\s*=|\bn\s*="),
    ("corr", r"corr(?:elation)?s?\b"),
]
# UNIT EQUIVALENCE — deliberately ONE pair, and only in the direction that cannot hide an error.
# A count of qualifying DAYS is the same quantity whether the writer calls them days or instances:
# evidence "16 of these fell in 2008", draft "16 of these days fell in 2008" — accurate, and it was
# hard-failing. day <-> count is therefore compatible. NOTHING else is: month/week/day stays strict
# (the months-vs-weeks bug this module exists to kill), and session stays strict against day because a
# trading session is not a calendar day.
_UNIT_EQUIV = {"day": {"count"}, "count": {"day"}}


_TIME_UNITS = {"session", "month", "week", "day", "year"}


def _unit_ok(value: float, unit: str, ev_pairs: set) -> bool:
    """Does (value, unit) bind, allowing only the day<->count equivalence above?

    The alias is REFUSED when the evidence also carries this value under a different TIME unit. The
    evidence side indexes a value under a neighbouring clause's unit as well as its own, so "recovery
    median 542 sessions" can also register 542 as a count — without this guard a draft writing "542
    days" would ride the count entry through the alias and the session-vs-day error would vanish.
    Caught by the self-test, not by inspection."""
    if (value, unit) in ev_pairs:
        return True
    for alt in _UNIT_EQUIV.get(unit, ()):
        if (value, alt) in ev_pairs:
            conflicting = {u for (v, u) in ev_pairs
                           if v == value and u in _TIME_UNITS and u != unit}
            return not conflicting
    return False


_DATE_RX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# Month-name dates in prose ("July 24th", "24 July") name the session the evidence already carries as an
# ISO date, so a draft that says so was hard-failing NO-MATCH on the bare day number — and naming the
# session is natural writing. Stripped before extraction so the digit never enters the numeric pool; the
# ISO date in the evidence remains the binding reference for the session itself.
_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
_PROSE_DATE_RX = re.compile(rf"\b(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\b"
                            rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\b", re.I)
# lookahead permits unit-fused forms ("14.0mo", "3.6-month"); digits/dots after are still barred so we
# never split "0.5" out of "0.51"
_NUM_RX = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\d.])")


def _prep(text: str) -> str:
    t = text.replace("−", "-").replace("–", "-")
    # Episode keys fuse a name to a year ("repricing_2022", "crash_2008", "calm_2013_2017"). Without
    # this split the year is not a year token to the extractor, so a draft that correctly writes "2022"
    # hard-fails NO-MATCH against evidence that visibly contains it (observed on recovery:ANCHOR_SPY,
    # 2026-07-24). markets-llm's answer_fidelity._normalize has carried this since its own encounter
    # with crash_2008; the shared core did not. Ported 2026-07-24.
    t = re.sub(r"(?<=[A-Za-z0-9])_(?=\d)", " ", t)
    t = _PROSE_DATE_RX.sub(" ", t)              # "July 24th" -> dropped; the ISO date carries the session
    t = re.sub(r"(?<=\d)\.\.(?=[\d-])", " to ", t)         # "0.5..14.0" range syntax -> "0.5 to 14.0"
    t = re.sub(r"(?m)^(\s*)\d+[.)]\s+", r"\1", t)          # markdown ordered-list markers are not data
    for p in _STRIP_PATTERNS:
        t = re.sub(p, " ", t, flags=re.I)
    return t


# ======================================================================================================
# THE CLAUSE BOUNDARY — ONE definition, used by EVERY window on BOTH sides.
#
# The same defect surfaced three times in three rounds, each in a different window, because each window
# carried its own ad-hoc cut:
#   1. the after-window captured a "%" from the FOLLOWING clause;
#   2. the evidence-side look-back reached across a NEWLINE and read the previous line's "%";
#   3. the draft-side look-back reached across a SENTENCE ("...beyond -3%. Of these, 35 occurred...").
# Patching windows one at a time guarantees a fourth. A unit is never inherited across a clause
# terminator, in either direction, in any window — and that is now stated once.
#
# DECIMALS ARE NOT BOUNDARIES: a period counts only when followed by whitespace or end-of-string, so
# "3.27%" keeps its unit while "-3%. Of these" does not leak across the full stop.
# ======================================================================================================
_CLAUSE_END_RX = re.compile(r"[;\n]|[.!?](?=\s|$)")


def _clause_after(t: str, pos: int, width: int) -> str:
    """Text from pos forward, stopping at the FIRST clause terminator."""
    w = t[pos:pos + width]
    m = _CLAUSE_END_RX.search(w)
    return w[:m.start()] if m else w


def _clause_before(t: str, pos: int, width: int) -> str:
    """Text before pos, starting AFTER the LAST clause terminator."""
    w = t[max(0, pos - width):pos]
    last = None
    for m in _CLAUSE_END_RX.finditer(w):
        last = m
    return w[last.end():] if last else w


def _unit_for(t: str, start: int, end: int, after: int) -> str | None:
    """AFTER-FIRST, clause-bounded unit resolution: units overwhelmingly trail their numbers ("-24.5%",
    "14.0mo", "range 0.5 to 14.0 months"); the before-window is a fallback for prefix forms ("corr 0.17").
    The after-window is cut at the clause boundary (';' or newline) so a '%' from the previous clause never
    captures the next clause's number."""
    wa = _clause_after(t, end, after)
    best, best_d = None, 10 ** 9
    for unit, rx in _UNIT_RX:
        m = re.search(rx, wa, re.I)
        if m and m.start() < best_d:
            best, best_d = unit, m.start()
    if best:
        return best
    # THE BEFORE-WINDOW NEEDS THE SAME CLAUSE CUT AS THE AFTER-WINDOW. It had none, so it reached back
    # across a NEWLINE: 25 chars before "35 of these fell in 2008" spans "  CRISIS CLUSTERING: " and
    # still catches the tail of the previous line — "...(SMH ETF proxy): -3.27%" — indexing a crisis
    # COUNT as a percentage. A draft writing "35 of these days" then collided with a phantom "35 pct".
    # A unit is never inherited across a clause boundary in either direction.
    wb = _clause_before(t, start, 25)
    for unit, rx in _UNIT_RX:
        for m in re.finditer(rx, wb, re.I):
            d = len(wb) - m.end()
            if d < best_d:
                best, best_d = unit, d
    return best


def _extract(text: str, wide_evidence: bool):
    """-> (tokens [{value, unit, raw, ctx}], dates set, years set)"""
    t = _prep(text)
    dates = set(_DATE_RX.findall(t))
    t = _DATE_RX.sub(" ", t)
    tokens, years = [], set()
    after = 60 if wide_evidence else 30
    for m in _NUM_RX.finditer(t):
        raw = m.group(0)
        v = abs(float(raw))
        ctx = t[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")
        if raw.lstrip("-").isdigit() and 1990 <= int(v) <= 2035 and "." not in raw:
            years.add(int(v))
            continue
        unit = _unit_for(t, m.start(), m.end(), after)
        tokens.append({"value": v, "unit": unit, "raw": raw, "ctx": ctx.strip()})
        if wide_evidence:
            # evidence-side generosity: when the PRECEDING clause names a different unit ("19 drawdowns ...
            # : 19 (deepest -35.2%"), index the value under BOTH — widens what a draft may bind to while
            # the draft side stays strictly adjacent (the months-vs-weeks class is still caught).
            wb = _clause_before(t, m.start(), 45)
            for u2, rx in _UNIT_RX:
                if u2 != unit and re.search(rx, wb, re.I):
                    tokens.append({"value": v, "unit": u2, "raw": raw, "ctx": ctx.strip()})
                    break
    for m in re.finditer(r"\b(" + "|".join(_WORD_NUMS) + r")\b", t, re.I):
        unit = _unit_for(t, m.start(), m.end(), 25)
        if unit:                                            # word numbers only count with an adjacent unit
            tokens.append({"value": float(_WORD_NUMS[m.group(1).lower()]), "unit": unit,
                           "raw": m.group(1), "ctx": t[m.start():m.end() + 25].replace("\n", " ")})
    years |= {int(d[:4]) for d in dates}
    return tokens, dates, years


# label -> (evidence-presence regex [case-sensitive], draft-presence regex [case-insensitive])
LABELS = {
    # deliberately NOT satisfied by a bare count ("five midterms") — a confident stat-account says that
    # too; the label demands the honesty framing itself.
    "SMALL-N": (r"SMALL-N",
                r"small[\s-]*n\b|anecdot|handful|not\s+a\s+(?:statistical\s+)?distribution|"
                r"(?:only|just)\s+(?:five|5|six|6)\b"),
    "SURVIVORSHIP": (r"SURVIVORSHIP", r"survivor"),
    "SINGLE-INSTANCE": (r"SINGLE[- ]INSTANCE",
                        r"single[\s-]instance|one\s+historical\s+(?:instance|episode)|n\s*=\s*1|"
                        r"each\s+(?:episode|regime|instance)\s+is\s+one"),
    # The optional list marker is load-bearing. Every evidence builder renders its required labels as
    # "  - CENSORED: ..." bullets, and the original anchor (^\s*CENSORED:) matched none of them — so the
    # label was never REQUIRED, and a draft that dutifully carried it was failed for INVENTING it. A rule
    # that punishes obedience. Observed twice in production (recovery:ANCHOR_SPY 2026-07-24, then
    # recovery:ANCHOR_NASDAQ in the first nightly). CENSORED is the only anchored label regex; the rest
    # match bare, which is why only this one was affected.
    "CENSORED": (r"(?m)^\s*(?:[-*]\s*)?CENSORED: |\[CENSORED",
                 r"censored|still\s+underwater|(?:never|not\s+yet)\s+recovered|unknown\s+recovery"),
    "INDEX-MEASURED": (r"INDEX-MEASURED",
                       r"index[\s-]measured|measured\s+on\s+the\s+(?:\w+\s+)?index|index\s+drawdowns|"
                       r"the\s+index\b|not\s+.{0,20}(?:any\s+)?(?:one|single)\s+stock"),
    "DISTRIBUTION": (r"LARGE-N", r"distribution"),
    "FORWARD-LOOKING": (r"FORWARD-LOOKING",
                        r"not\s+a\s+(?:prediction|forecast)|no\s+(?:prediction|forecast)|"
                        r"(?:doesn'?t|does\s+not|cannot|can'?t)\s+(?:predict|forecast|tell)|"
                        r"inference|history\b[^.]{0,40}not\s+a\s+guarantee|forward[\s-]looking"),
    "SECTOR-PROXY": (r"SECTOR-PROXY", r"proxy|\betf\b"),
    # DETECTION WAS THE PROBLEM, NOT THE LABEL. The label is exactly right on a crossing-led digest —
    # sections 3/4 ARE conditional distributions. But the presence regex demanded "not a forecast"
    # contiguously, so a draft closing with "cannot be interpreted as a forecast of future market
    # behavior" and "does not predict tomorrow's movements" was failed for omitting a caveat it had
    # plainly made. A FALSE POSITIVE. The label stays required; natural deferral phrasing now satisfies
    # it, including plurals, "cannot be interpreted as", and "does not predict".
    "NOT-A-SIGNAL": (r"NOT-A-SIGNAL",
                     r"not[\s-]a[\s-]signal"
                     r"|\bnot\b[^.]{0,40}\b(?:forecasts?|predictions?|recommendations?|probabilit)"
                     r"|\b(?:cannot|can'?t|does\s+not|do\s+not|doesn'?t|won'?t|will\s+not)\b"
                     r"[^.]{0,60}\b(?:forecast|predict|guarantee|recommend|tell\s+you|imply)"
                     r"|what\s+followed|describes?\s+the\s+past|no(?:t)?\s+(?:a\s+)?guarantee"
                     r"|historical\s+outcomes?,?\s+not"),
}

# --- MEDIAN-WITHOUT-N (Daily Measured Digest, D1-4) -------------------------------------------------
# A conditional distribution's median is meaningless alone: "the median next session was +0.2%" reads as
# a forecast, while "+0.2%, positive in 25 of 46 instances, N=46" reads as what it is — a spread of
# outcomes. The digest evidence block therefore states the rule to the drafter, and this check makes it
# a HARD FAIL rather than a hope. Two failure classes:
#   MEDIAN-WITHOUT-N  a sentence gives a median but no N and no hit rate in that SAME sentence.
#   BARE-AVERAGE      a sentence reports a mean/average of outcomes at all — forbidden outright for this
#                     class, because averaging a distribution whose whole point is its spread destroys it.
# Scoped to drafts whose evidence carries NOT-A-SIGNAL (i.e. digest-class drafts): applying it to every
# study would fail legitimate prose about a median drawdown depth, which is a different kind of number.
_MEDIAN_RX = re.compile(r"\bmedian\b", re.I)
# "median" is not always a reported statistic. The INDEX-MEASURED label the drafter is REQUIRED to carry
# says "shallower than the median single stock's" — median as an adjective for a typical entity, carrying
# no value at all. Failing that draft would punish it for obeying a mandatory instruction (observed in the
# D1 validation gate, first live digest). A median is REPORTED only when a number rides with it.
_MEDIAN_ADJ_RX = re.compile(r"\bmedian\s+(?:single|individual|typical|average|ordinary)?\s*"
                            r"(?:stock|name|company|firm|share|issuer)\b", re.I)
_ANY_NUM_RX = re.compile(r"-?\d+(?:\.\d+)?")


# A median's companion depends on WHAT IS BEING MEASURED, and getting this wrong made the rule
# unsatisfiable. A forward RETURN has a hit rate (count positive / N) because an outcome can be positive
# or negative. A recovery DURATION has no such thing — "positive" is meaningless for a number of sessions,
# and the evidence block prints no hit rate anywhere in Section 4. Demanding one there forced the drafter
# to either fail or fabricate; a rule whose only satisfying move is inventing a number is a broken rule.
# The purpose survives in both cases: a median never stands alone. Returns carry hit rate + N; durations
# carry N + range.
_DURATION_RX = re.compile(r"\bsessions?\b|\bdays?\b|\bmonths?\b|\bweeks?\b|\byears?\b", re.I)
_RANGE_RX = re.compile(r"\brang\w+\b|\brange\b|\bfrom\s+[\d.]+\s+to\s+[\d.]+|[\d.]+\s+to\s+[\d.]+", re.I)


def _median_kind(sent: str, pos: int) -> str:
    """'duration' | 'return' — what the median at `pos` measures, from the words riding with it."""
    window = sent[pos:pos + 70]
    for sep in (";", "]", "\n"):
        cut = window.find(sep)
        if cut >= 0:
            window = window[:cut]
    if _DURATION_RX.search(window) and "%" not in window:
        return "duration"
    return "return"


def _median_is_reported(sent: str) -> bool:
    """Does this sentence REPORT a median value (vs. use 'median' as an adjective)? Clause-bounded, so a
    number from a later clause cannot make an adjectival 'median' look like a statistic."""
    for m in re.finditer(r"\bmedian\b", sent, re.I):
        if _MEDIAN_ADJ_RX.match(sent, m.start()):
            continue
        after = sent[m.end():m.end() + 60]
        for sep in (";", "]", "\n"):
            cut = after.find(sep)
            if cut >= 0:
                after = after[:cut]
        before = sent[max(0, m.start() - 30):m.start()]
        if _ANY_NUM_RX.search(after) or _ANY_NUM_RX.search(before):
            return True
    return False
_HITRATE_RX = re.compile(r"\bhit[\s-]rate\b|\d+\s+of\s+\d+|positive\s+in\b|\bN\s*=\s*\d+", re.I)
# Intervening words are normal English: "Across all 261 RECOVERED instances", "over 46 recovered
# instances". The original demanded the noun immediately after the digit, so a sentence plainly
# carrying N=261 was failed for omitting it — a FALSE POSITIVE, found by verifying the rule
# rather than attributing the failure to the drafter. Up to two modifiers are now tolerated.
_N_RX = re.compile(r"\bN\s*=\s*\d+"
                   r"|\b\d+\s+of\s+\d+\b"
                   # "over 46 recovered instances", "Across all 261 recovered instances" — up to
                   # two modifiers between the digit and its noun, which is ordinary English.
                   # "from" is deliberately ABSENT: "from 2 to 2544 sessions" is a RANGE, and
                   # admitting it would let a sentence with no N at all pass (a false negative
                   # traded for the false positive — caught by testing both directions).
                   r"|\b(?:over|across|among)\s+(?:all\s+)?\d+\s+(?:\w+\s+){0,2}"
                   r"(?:instances?|episodes?|samples?|cases?|drawdowns?|sessions?|days?)\b"
                   # a bare count noun, but NOT sessions/days: "2544 sessions" is a duration.
                   r"|\b\d+\s+(?:\w+\s+){0,2}(?:instances?|episodes?|samples?|cases?|drawdowns?)\b",
                   re.I)
# "average"/"mean" as a statistic. Excludes idioms that are not the statistic ("on average" alone still
# counts — it is exactly the hedge this class must not use; "meanwhile"/"meaningful" are word-boundary
# safe, and "means" as a verb is excluded explicitly).
_AVERAGE_RX = re.compile(r"\baverage[ds]?\b|\baverage\b|\bmean\b(?!\s*(?:s\b|ing\b|t\b))", re.I)
_WS_RX = re.compile(r"\s+")


def _is_evidence_text(sentence: str, match: re.Match, evidence: str) -> bool:
    """Is the flagged word part of text the EVIDENCE ITSELF mandates the draft carry?

    The CENSORED label reads "recovery time UNKNOWN, never imputed or AVERAGED in" — a phrase whose
    whole content is a prohibition on averaging, which the drafter is REQUIRED to carry. Failing a
    draft for reproducing it is the fourth instance of this module penalising obedience, so the check
    now asks whether the surrounding phrase is verbatim evidence before firing. Deliberately a WINDOW,
    not the whole sentence: quoting a mandated phrase is protected, wrapping "the average was 0.2%"
    inside an otherwise-quoted sentence is not."""
    def norm(s: str) -> str:
        return _WS_RX.sub(" ", re.sub(r"[^0-9a-z ]+", " ", s.lower())).strip()

    # Window runs BACKWARD from the match and stops at it: the distinguishing text is what precedes
    # the word, and anything after it risks trailing punctuation or the next sentence's first word
    # (which is exactly what defeated the first attempt at this check).
    lo = max(0, match.start() - 34)
    window = norm(sentence[lo:match.end()])
    window = window.split(" ", 1)[1] if " " in window else window      # drop a clipped leading word
    return len(window) >= 12 and window in norm(evidence)


# --- CAUSAL CLAIMS (Daily Measured Digest, D1-4) ----------------------------------------------------
# The digest reports co-movement and NOTHING ELSE: the engine measures what moved on a session, never
# why. Every other check passes a causal sentence — "consumer discretionary fell -4.61%, driven by the
# 6.17% rise in crude" binds every number and carries every label, so numeric binding and label
# completeness both wave it through. Yet it is the single most damaging thing this format could print,
# because it is the claim the evidence most conspicuously does not contain. Deterministic, and scoped to
# digest-class evidence so study pieces (which legitimately discuss mechanisms) are untouched.
#
# The list is EXPLICIT CAUSAL VOCABULARY only. Bare "as" and "after" are excluded: they are overwhelmingly
# temporal in this register ("as measured", "after the close") and flagging them would train the writer to
# fight the checker rather than the claim. "amid" and "on the back of" ARE included — they are causal
# assertions wearing a hedge, which is exactly the move this class must not make.
# "reflect" was REMOVED after producing only false positives in production: "factors not reflected in
# this data set" (a coverage disclaimer) and "this record reflects settled prices at the close" (a
# description of what the data IS). Its genuine causal use ("the move reflects concern") is always
# accompanied by a stronger marker, so nothing is lost. A rule that only ever fires wrongly is worse
# than no rule: it teaches the writer to fight the checker instead of the claim.
_CAUSAL_RX = re.compile(
    r"\b(?:drove|driven\s+by|caused|causing|triggered|sparked|fuel(?:l?ed)|led\s+to|"
    r"explains?|explained\s+by|respond(?:ed|ing)\s+to|in\s+response\s+to|"
    r"because\s+of|due\s+to|thanks\s+to|owing\s+to|on\s+the\s+back\s+of|attributable\s+to|"
    r"blamed\s+on|result(?:ed|ing)\s+from|prompted\s+by|weighed\s+on|dragged\s+(?:down\s+)?by|"
    # amid(?:st)? — NOT "amidst?", which parses as "amids" + optional "t" and silently stops matching
    # plain "amid". A draft titled "...Steady Amidst Global Shifts" slipped a causal connective past the
    # rule through the -st variant; the first fix for it broke the base word instead.
    r"boosted\s+by|lifted\s+by|pressured\s+by|amid(?:st)?)\b|\b\w+-driven\b", re.I)


def _digest_class(evidence: str) -> bool:
    """Is this the conditional-distribution class the median and causal rules govern?"""
    return bool(re.search(r"NOT-A-SIGNAL|MEASURED DAILY DIGEST EVIDENCE", evidence))


# --- COMPLETENESS (Daily Measured Digest, D1-4) -----------------------------------------------------
# Every other check validates what the draft SAYS. None of them notice what it never got to. The first
# passing digest ended mid-sentence at "...full range -4.31% to 4.64%," with Section 4 absent entirely,
# and scored a clean pass: every number it managed to write bound correctly, every label was present.
# A truncated post is unpublishable no matter how honest its surviving sentences are.
# The four headings are VERBATIM and MANDATORY, and the check now requires a real markdown heading
# ("## The mark"), not the words appearing anywhere in running prose. A draft that buried Section 4's
# numbers in a paragraph with no header passed the looser content-based test while being unscannable —
# the format is part of the product, not decoration. Sections 1 and 2 exist in EVERY digest; 3 and 4
# only when the evidence carries a crossing, so their requirement is still evidence-driven.
DIGEST_HEADINGS = ["The mark", "The context", "Next session", "Full recovery"]
_SECTION_REQUIRED = [(None, r"(?mi)^\s{0,3}#{1,4}\s*the\s+mark\b"),
                     (None, r"(?mi)^\s{0,3}#{1,4}\s*the\s+context\b"),
                     ("SECTION 3", r"(?mi)^\s{0,3}#{1,4}\s*next\s+session\b"),
                     ("SECTION 4", r"(?mi)^\s{0,3}#{1,4}\s*full\s+recovery\b")]
_TERMINAL_RX = re.compile(r"[.!?][\"')\]]*\s*$")


def check_completeness(draft: str, evidence: str) -> list[dict]:
    """-> list of failures. Section presence is driven by the EVIDENCE: a quiet session legitimately has
    no Section 3/4, and demanding them there would be the opposite error."""
    if not _digest_class(evidence):
        return []
    out = []
    body = draft.rstrip()
    if body and not _TERMINAL_RX.search(body):
        out.append({"type": "TRUNCATED-DRAFT", "token": "end-of-draft",
                    "detail": "the draft does not end on a complete sentence — generation was cut off. "
                              f"tail: ...{body[-90:]!r}"})
    for i, (marker, heading_rx) in enumerate(_SECTION_REQUIRED):
        # marker None -> always required; otherwise required only when the evidence carries that section
        if marker is not None and marker not in evidence:
            continue
        if not re.search(heading_rx, draft):
            want = DIGEST_HEADINGS[i]
            out.append({"type": "MISSING-SECTION", "token": want,
                        "detail": f'the draft has no "## {want}" HEADING. The numbers may be present '
                                  f"in running prose — the format is still wrong. The four headings "
                                  f"are verbatim and mandatory: "
                                  + ", ".join(f'"## {h}"' for h in DIGEST_HEADINGS)})
    return out


def check_causal_claims(draft: str, evidence: str) -> list[dict]:
    """-> list of failures. A digest may state that two things moved on the same session; it may never
    state or imply that one moved the other."""
    if not _digest_class(evidence):
        return []
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", draft):
        s = sent.strip()
        m = _CAUSAL_RX.search(s)
        # The evidence's own NO-CAUSATION instruction contains the very words this rule forbids ("do not
        # write that one caused, drove, triggered..."), so a draft that recites it fires CAUSAL-CLAIM for
        # exactly the wrong reason. Fifth occurrence of this module penalising recited mandatory text —
        # _is_evidence_text existed for it and was wired into the average check only. Reciting the block
        # is still a defect: INSTRUCTION-RECITATION catches it, with the right message.
        if m and not _is_evidence_text(s, m, evidence):
            out.append({"type": "CAUSAL-CLAIM", "token": m.group(0),
                        "detail": f"causal language in a digest — the evidence measures co-movement, "
                                  f"never cause. Say what moved and stop. sentence: {s[:180]}"})
    return out


# --- INSTRUCTION RECITATION (Daily Measured Digest) -------------------------------------------------
# A draft pasted "[NOT-A-SIGNAL: These series moved on the same session; do not write that one caused,
# drove, triggered, or explains another — the evidence contains no such measurement.]" into its prose.
# That is a defect on its own terms, independent of any other check: a reader who opens a published
# digest and finds raw instruction text is worse served than by the causal claim the instruction was
# forbidding. Label text is a CONSTRAINT ON THE WRITING, never content to reproduce — the piece states
# its caveats in its own words or not at all.
#
# Detection is verbatim-span based rather than keyword based: a run of >= MIN_RECITED_WORDS consecutive
# words lifted from an evidence line that is an INSTRUCTION (imperative/prohibition), not a data line.
# Numbers and short label names are explicitly NOT recitation — quoting figures is the entire job, and
# naming a label is required.
MIN_RECITED_WORDS = 9
_INSTRUCTION_HINT = re.compile(r"\bdo not\b|\bnever\b|\bmandatory\b|\bstate this\b|\bsay so\b|"
                               r"\bforbidden\b|\bdo NOT\b|\blead with\b|\bomit\b", re.I)


def check_instruction_recitation(draft: str, evidence: str) -> list[dict]:
    """-> list of failures. Flags prose that reproduces the evidence's INSTRUCTION text verbatim."""
    if not _digest_class(evidence):
        return []
    instr_lines = [ln.strip() for ln in evidence.splitlines() if _INSTRUCTION_HINT.search(ln)]
    if not instr_lines:
        return []

    def words(s):
        return re.sub(r"[^0-9a-z ]+", " ", s.lower()).split()

    d_words = words(draft)
    d_join = " ".join(d_words)
    for ln in instr_lines:
        lw = words(ln)
        for i in range(0, max(0, len(lw) - MIN_RECITED_WORDS) + 1):
            span = " ".join(lw[i:i + MIN_RECITED_WORDS])
            if span and span in d_join:
                return [{"type": "INSTRUCTION-RECITATION", "token": span[:60],
                         "detail": "the draft reproduces the evidence block's INSTRUCTION text verbatim "
                                   "— label text is a constraint on the writing, not content to publish. "
                                   "State the caveat in your own words. recited: \"" + span[:110] + "\""}]
    return []


def check_median_discipline(draft: str, evidence: str) -> list[dict]:
    """-> list of failures. Sentence-scoped: the hit rate and N must sit in the SAME sentence as the
    median, because a reader takes the number from the sentence they are reading, not from a paragraph
    three sentences down."""
    if not _digest_class(evidence):
        return []
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", draft):
        s = sent.strip()
        if not s:
            continue
        if _median_is_reported(s):
            m = re.search(r"\bmedian\b", s, re.I)
            kind = _median_kind(s, m.end()) if m else "return"
            if kind == "duration":
                if not (_N_RX.search(s) and _RANGE_RX.search(s)):
                    out.append({"type": "MEDIAN-WITHOUT-N", "token": "median (duration)",
                                "detail": "a median recovery time must carry its N and its range in "
                                          "the same sentence (a hit rate does not exist for a "
                                          f"duration). sentence: {s[:180]}"})
            elif not (_HITRATE_RX.search(s) and _N_RX.search(s)):
                out.append({"type": "MEDIAN-WITHOUT-N", "token": "median (return)",
                            "detail": "a median return must carry its hit rate AND N in the same "
                                      f"sentence — a bare median reads as a forecast. sentence: {s[:180]}"})
        m = _AVERAGE_RX.search(s)
        if m and not _is_evidence_text(s, m, evidence):
            out.append({"type": "BARE-AVERAGE", "token": "average/mean",
                        "detail": "averages are forbidden for conditional distributions — report the "
                                  f"median with its hit rate, N and range. sentence: {s[:180]}"})
    return out

# INVENTED-LABEL detection — deliberately NARROW (explicit label invocation only) where required-label
# satisfaction above is BROAD. The asymmetry is the point: a draft may honestly write "not a distribution"
# on a SMALL-N study or mention "the index" without claiming INDEX-MEASURED, but writing the label term
# itself asserts a caveat, and a caveat the evidence never carried is a false claim — same class as an
# invented number. (DISTRIBUTION's claim regex is LARGE-N only, because honest SMALL-N drafts are
# INSTRUCTED to say "not a distribution"; SURVIVORSHIP is broad because "survivor" is unambiguous
# label-speak in this publication's vocabulary.)
LABEL_CLAIMS = {
    "SMALL-N": r"\bsmall[\s-]*n\b",
    "SURVIVORSHIP": r"survivor",
    "SINGLE-INSTANCE": r"\bsingle[\s-]instance\b|\bn\s*=\s*1\b",
    "CENSORED": r"\bcensored\b",
    "INDEX-MEASURED": r"\bindex[\s-]measured\b",
    "DISTRIBUTION": r"\blarge[\s-]*n\b",
    "FORWARD-LOOKING": r"\bforward[\s-]looking\b",
    "SECTOR-PROXY": r"\bsector[\s-]proxy\b",
    "NOT-A-SIGNAL": r"\bnot[\s-]a[\s-]signal\b",
}

# INVENTED-LABEL fires on ASSERTIONS, not on mentions that DENY the label applies. A draft wrote "nor
# does it address censored instances or survivorship limitations" — correctly noting they are absent —
# and was failed for asserting both. Same class as the recitation and average fixes: the rule read a
# word rather than a claim. Negation is detected in the clause LEADING UP TO the mention, which is where
# English puts it ("does not address X", "no X here", "without any X", "cannot speak to X").
_NEGATION_RX = re.compile(
    r"\b(?:no|not|never|nor|neither|none|nothing|nowhere|without|absent|lacks?|lacking|excludes?|"
    r"does\s+not|do\s+not|doesn'?t|don'?t|cannot|can'?t|is\s+not|are\s+not|isn'?t|aren'?t|"
    r"free\s+of|unaffected\s+by|inapplicable|not\s+applicable|n/?a)\b", re.I)


def _label_mention_is_negated(draft: str, match: re.Match) -> bool:
    """Is this label mention DENIED rather than asserted? Looks back to the start of the clause."""
    start = match.start()
    lo = max(0, start - 140)
    window = draft[lo:start]
    for sep in (". ", "! ", "? ", "\n", "; "):
        cut = window.rfind(sep)
        if cut >= 0:
            window = window[cut + len(sep):]
    return bool(_NEGATION_RX.search(window))


_ATTRIB_RX = re.compile(r"measured|relational engine|the engine|since 2004|the data|this study|"
                        r"across (?:the )?\d+|distribution", re.I)
_DIRECTIONAL_RX = re.compile(r"\b(?:rise[sn]?|rising|rose|climb\w*|rall(?:y|ies|ied)|gain\w*|"
                             r"outperform\w*|underperform\w*|upward|downward|tend\w*|drift\w*|higher|"
                             r"lower|fall\w*|fell|drop\w*|beat|sink\w*|surge\w*)\b", re.I)


def run_fidelity(draft: str, evidence: str) -> dict:
    """-> {passed, failures[], labels{}, numeric[], directional[]} — deterministic."""
    ev_tokens, ev_dates, ev_years = _extract(evidence, wide_evidence=True)
    ev_pairs = {(t["value"], t["unit"]) for t in ev_tokens if t["unit"]}
    ev_values = {t["value"] for t in ev_tokens}
    d_tokens, d_dates, d_years = _extract(draft, wide_evidence=False)

    failures, numeric = [], []
    for d in d_dates:
        ok = d in ev_dates
        numeric.append({"raw": d, "unit": "date", "status": "ok" if ok else "NO-MATCH", "ctx": d})
        if not ok:
            failures.append({"type": "NO-MATCH", "token": d, "detail": "date not in evidence"})
    for y in d_years:
        ok = y in ev_years or float(y) in ev_values
        numeric.append({"raw": str(y), "unit": "year", "status": "ok" if ok else "NO-MATCH", "ctx": str(y)})
        if not ok:
            failures.append({"type": "NO-MATCH", "token": str(y), "detail": "year not in evidence"})
    for t in d_tokens:
        v, u = t["value"], t["unit"]
        if u and _unit_ok(v, u, ev_pairs):
            st = "ok"
        elif u and v in ev_values:
            other = sorted({eu for (evv, eu) in ev_pairs if evv == v})
            st = "UNIT-MISMATCH"
            failures.append({"type": "UNIT-MISMATCH", "token": f"{t['raw']} {u}",
                             "detail": f"evidence has {t['raw']} only as {other or ['(unitless)']} — "
                                       f"draft says {u}. ctx: {t['ctx']}"})
        elif not u and (v in ev_values or v in ev_years):
            st = "ok"
        else:
            st = "NO-MATCH"
            failures.append({"type": "NO-MATCH", "token": f"{t['raw']} {u or ''}".strip(),
                             "detail": f"no evidence number matches. ctx: {t['ctx']}"})
        numeric.append({"raw": t["raw"], "unit": u, "status": st, "ctx": t["ctx"]})

    labels = {}
    for name, (ev_rx, dr_rx) in LABELS.items():
        required = bool(re.search(ev_rx, evidence))
        present = bool(re.search(dr_rx, draft, re.I)) if required else None
        labels[name] = {"required": required, "present": present}
        if required and not present:
            failures.append({"type": "MISSING-LABEL", "token": name,
                             "detail": f"evidence carries {name}; draft never states it"})
    for name, claim_rx in LABEL_CLAIMS.items():
        if labels[name]["required"]:
            continue
        m = re.search(claim_rx, draft, re.I)
        if not m or _label_mention_is_negated(draft, m):
            continue
        labels[name]["invented"] = True
        failures.append({"type": "INVENTED-LABEL", "token": name,
                         "detail": f"draft asserts {name} but the evidence never carries it — "
                                   f"a false caveat is a false claim, same class as a false number"})

    failures.extend(check_median_discipline(draft, evidence))
    failures.extend(check_causal_claims(draft, evidence))
    failures.extend(check_completeness(draft, evidence))
    failures.extend(check_instruction_recitation(draft, evidence))

    directional = []
    sents = re.split(r"(?<=[.!?])\s+", draft)
    _ext_cache: dict[int, tuple] = {}

    def _sent_nums(i: int):
        if i not in _ext_cache:
            tk, dd, yy = _extract(sents[i], wide_evidence=False)
            _ext_cache[i] = (tk, bool(tk or dd or yy))
        return _ext_cache[i]

    for i, sent in enumerate(sents):
        if not (_ATTRIB_RX.search(sent) and _DIRECTIONAL_RX.search(sent)):
            continue
        s_tokens, has_own_numbers = _sent_nums(i)
        # scope gate: a directional sentence with NO numbers of its own is flagged only when an ADJACENT
        # sentence makes an engine-attributed NUMERIC claim (the "upward drift" embellishment rides right
        # next to the stat it embellishes); number-free narrative framing with number-free neighbors is
        # editorial voice, not a checkable claim.
        if not has_own_numbers:
            if not any(_ATTRIB_RX.search(sents[j]) and _sent_nums(j)[1]
                       for j in (i - 1, i + 1) if 0 <= j < len(sents)):
                continue
        bound = all((tk["unit"] and _unit_ok(tk["value"], tk["unit"], ev_pairs))
                    or (not tk["unit"] and (tk["value"] in ev_values or tk["value"] in ev_years))
                    for tk in s_tokens)
        directional.append({"sentence": sent.strip()[:300], "numbers_bound": bound})

    return {"passed": not failures, "failures": failures, "labels": labels,
            "numeric": numeric, "directional": directional}
