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
    # "w" joined 2026-07-30, for symmetry with "mo" one line above. The recovery evidence renders short
    # spans as "1w" ("range 1w-67.2mo"), so the months side of that very range bound and the weeks side
    # did not — and every draft that expanded it into "1 week" hard-failed UNIT-MISMATCH. Measured on the
    # live KOSPI piece: "1 week" failed all four attempts, and 20 distinct week-form range strings sit
    # across the anchors, so this blocked the recovery class generally, not one study. Alternation is
    # left-to-right and "week"/"wk" are listed first, so the bare-w branch only ever catches the "1w"
    # form; \b keeps it off any word merely starting with w.
    ("week", r"weeks?\b|wks?\b|w\b"),
    ("day", r"days?\b"),
    ("year", r"years?\b|yrs?\b"),
    # "session" is its OWN unit, deliberately NOT folded into count. A trading session is not a calendar
    # day: "542 sessions" is ~2.2 years, "542 days" is ~1.5. Keeping them distinct means a draft that
    # writes days where the evidence says sessions still hard-fails, which is the whole point of unit
    # binding. (The digest denominates both its horizons and its recovery times in sessions, so the
    # lexicon has to know the word — without it, "over the next 20 sessions was 1.73%" resolved 20 to
    # PCT from the trailing figure and failed every digest that stated a horizon in prose.)
    ("session", r"sessions?\b"),
    # "analogs?" joined 2026-07-27: without it, "fifteen notable analogs" carried no adjacent unit,
    # so the word-number was never extracted and an invented count of the analog set sailed through
    # THREE digest drafts (the digit form was caught; the model routed to the word form). With the
    # noun in the lexicon, both "150 analogs" (binds) and "fifteen analogs" (NO-MATCH) resolve.
    ("count", r"events?\b|meetings?\b|midterms?\b|elections?\b|episodes?\b|cases?\b|instances?\b|"
              r"drawdowns?\b|anecdotes?\b|stocks?\b|names?\b|(?:data\s+)?points?\b|occurrences?\b|"
              r"cycles?\b|samples?\b|analogs?\b|\bN\s*=|\bn\s*="),
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
    # PHRASING-AUDITED 2026-07-27 (see LABEL_PHRASINGS in scripts/digest_selftest.py). Third
    # occurrence of the narrow-presence defect closed as a CLASS rather than one label at a time:
    # every label below was tested against the phrasings a draft would actually use. Presence stays
    # BROAD (accept the honest caveat however it is worded); LABEL_CLAIMS stays NARROW (invention is
    # only ever the explicit label term). That asymmetry is the design, not an oversight.
    "SURVIVORSHIP": (r"SURVIVORSHIP",
                     r"survivor|blew\s+up|failed\s+(?:companies|names|firms)|biased\s+short|"
                     r"(?:absent|missing)\s+from\s+the\s+(?:sample|panel)|"
                     r"drop(?:ped|ping)?\s+out\s+of\s+the\s+panel|"
                     r"still\s+underwater[^.]{0,40}cannot\s+be\s+counted"),
    # SURVIVOR-SELECTED (single-name pairs slice, 2026-07-27): the SELECTION is the survivorship —
    # a bare-ticker side is studied because it survived and dominated. Presence demands the
    # selection CONCEPT, not the bare word "survivor" (which satisfies plain SURVIVORSHIP and says
    # nothing about why the name is in the study at all).
    "SURVIVOR-SELECTED": (r"SURVIVOR-SELECTED",
                          r"survivor[\s-]selected|survived\s+and\s+dominated|"
                          r"because\s+(?:it|they)\s+survived|selected\s+because|"
                          r"studied\s+because|by\s+construction\s+of\s+the\s+selection|"
                          r"not\s+the\s+odds\s+for\s+a\s+name|"
                          r"selection\s+(?:itself\s+)?is\s+the\s+survivorship|"
                          r"winner'?s\s+history|did\s+not\s+make\s+it\s+are\s+not"),
    "SINGLE-INSTANCE": (r"SINGLE[- ]INSTANCE",
                        r"single[\s-]instance|one\s+historical\s+(?:instance|episode)|n\s*=\s*1|"
                        r"(?:each|every)\s+(?:episode|regime|instance|case|figure)\s+"
                        r"(?:here\s+)?is\s+one|is\s+a\s+single\s+instance|one\s+sample\s+per"),
    # The optional list marker is load-bearing. Every evidence builder renders its required labels as
    # "  - CENSORED: ..." bullets, and the original anchor (^\s*CENSORED:) matched none of them — so the
    # label was never REQUIRED, and a draft that dutifully carried it was failed for INVENTING it. A rule
    # that punishes obedience. Observed twice in production (recovery:ANCHOR_SPY 2026-07-24, then
    # recovery:ANCHOR_NASDAQ in the first nightly). CENSORED is the only anchored label regex; the rest
    # match bare, which is why only this one was affected.
    # Presence accepts the natural statements of censoring, not just the two word-orders first
    # imagined. "Seven instances have NOT regained their prior high — recovery time remains UNKNOWN"
    # is a complete, honest carry of the label and was hard-failed MISSING-LABEL for word order
    # (2026-07-27, third live draft of the rebuilt digest) — the NOT-A-SIGNAL lesson again:
    # detection was the problem, not the label. INVENTED-LABEL detection stays narrow (explicit
    # "censored" only), so broadening presence cannot create false invented-label fires.
    "CENSORED": (r"(?m)^\s*(?:[-*]\s*)?CENSORED: |\[CENSORED",
                 r"censored|still\s+underwater|(?:never|not\s+yet)\s+recovered|unknown\s+recovery"
                 r"|(?:not|never)\s+(?:yet\s+)?regained|recovery\s+time[^.]{0,40}\bunknown"),
    # "shallower ... than ... an individual stock" IS the label's whole content in natural words —
    # four consecutive honest quiet-note drafts were failed for phrasing it that way (2026-07-27;
    # the NOT-A-SIGNAL lesson a third time: detection was the problem, not the label).
    "INDEX-MEASURED": (r"INDEX-MEASURED",
                       r"index[\s-]measured|measured\s+on\s+the\s+(?:\w+\s+)?index|index\s+drawdowns|"
                       r"the\s+index\b|"
                       r"not\s+.{0,20}(?:any\s+)?(?:one|single)\s+(?:stock|name|company)|"
                       r"not\s+what\s+(?:any\s+)?one\s+(?:stock|name|company)|"
                       r"shallower[^.]{0,60}\b(?:stocks?|names?|compan(?:y|ies))\b"),
    # DELIBERATELY BROAD, after trying the alternative and MEASURING it. A negation-safe variant was
    # written first (accept "distribution" only in affirmative constructions) to stop "not a
    # distribution" — the sentence a SMALL-N draft is instructed to write — from satisfying a LARGE-N
    # requirement. Re-scoring the whole queue showed that variant produced TWO false failures on
    # already-published notes ("This distribution captures observed behavior…", "this observed
    # distribution does not guarantee…") and ZERO true catches: the "rule that only ever fires
    # wrongly" signature this module already refuses elsewhere. Reverted.
    # The residual hole is real but small and belongs elsewhere: a LARGE-N draft asserting "not a
    # distribution" is making a FALSE CHARACTERISATION, which is a content error, not an absent
    # caveat — presence detection's job is only whether the caveat was made. Note that a general
    # negation guard on presence would be actively wrong: most honest labels are stated in negative
    # form ("not a forecast", "never recovered", "nor is it a ranking"), so rejecting negated matches
    # would break NOT-A-SIGNAL, FORWARD-LOOKING, CENSORED and NOT-A-RANKING at once. DISTRIBUTION is
    # the only affirmative-form label in the set, which is why the problem looks general and isn't.
    "DISTRIBUTION": (r"LARGE-N", r"distribution"),
    "FORWARD-LOOKING": (r"FORWARD-LOOKING",
                        r"not\s+a\s+(?:prediction|forecast)|no\s+(?:prediction|forecast)|"
                        r"(?:doesn'?t|does\s+not|cannot|can'?t)\s+(?:predict|forecast|tell)|"
                        r"inference|history\b[^.]{0,40}not\s+a\s+guarantee|forward[\s-]looking|"
                        r"does\s+not\s+guarantee|nothing\s+(?:here\s+)?(?:predicts|guarantees)|"
                        r"no\s+basis\s+for\s+predicting"),
    "SECTOR-PROXY": (r"SECTOR-PROXY",
                     r"proxy|\betf\b|exchange[\s-]traded\s+fund|"
                     r"stand(?:s|ing)?\s+in\s+for\s+the\s+sector"),
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
    # NOT-A-RANKING was a STRUCTURAL HOLE, found by the 2026-07-27 class audit: the sector-
    # comparative builder has emitted it as a mandatory label since the sector×event work, and the
    # checker had no entry at all — so it was never required and never guarded against invention.
    # Exactly the latent case the class treatment exists to surface (the unit-notation and
    # digit-bearing-name audits each found one too).
    "NOT-A-RANKING": (r"NOT-A-RANKING",
                      # THE LABEL'S OWN NAME COMES FIRST. The first draft of this entry required a
                      # SPACE after "not", so the hyphenated label term "NOT-A-RANKING" — which three
                      # already-published notes state verbatim — did not match its own presence
                      # regex. Caught by re-scoring the queue before commit; it is the very defect
                      # this audit exists to close, committed inside the fix for it. Every label
                      # regex must accept the label term itself, hyphens included.
                      r"not[\s-]a[\s-]ranking|(?:nor|not)\s+is\s+it\s+a[\s-]ranking|"
                      r"(?:is|are|was)n'?t\s+a[\s-]ranking|"
                      r"not\s+a\s+recommendation|not\s+a\s+buy\s+list|\bbuy\s+list\b|"
                      r"is\s+not\s+predicted\s+to|what\s+to\s+(?:buy|avoid|hold)|"
                      r"ordering\s+is\s+not|not\s+(?:a\s+)?(?:forecast|prediction)\s+of\s+what\s+to"),
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
# The numeric branches carried [\d.]+ with NO SIGN, so "from -7.3% to -24.5%" did not read as a range
# — and a drawdown range is negative at BOTH ends, which makes this the commonest range the publication
# writes. It survived only because "ranging"/"range" usually rides along; a sentence saying "the spread
# ran from -7.3% to -24.5%" had no range at all as far as the checker was concerned. Fifth recall gap
# found 2026-07-31, and the first found by a selftest fixture rather than by corpus or incident.
_RANGE_RX = re.compile(r"\brang\w+\b|\brange\b|\bspread\b|\bspann\w+\b"
                       r"|\bfrom\s+-?[\d.]+%?\s+to\s+-?[\d.]+|-?[\d.]+%?\s+to\s+-?[\d.]+", re.I)


# A median DEPTH is not a median return. Every drawdown is negative by construction, so "positive in
# 3 of 5" is not a statistic that exists for it — demanding a hit rate there is the same category
# error the duration branch already avoids ("a hit rate does not exist for a duration"). Found
# 2026-07-31: ungating the rule made it fire on nine published sentences of the form "a median
# drawdown depth of -15.7%", every one of them honest. Depth carries N and range, like duration.
_DEPTH_RX = re.compile(r"\bdrawdowns?\b|\bdepths?\b|\bdeclines?\b|\bfalls?\b|\btroughs?\b|"
                       r"\bpeak-to-trough\b|\bselloffs?\b", re.I)


def _median_kind(sent: str, pos: int) -> str:
    """'duration' | 'depth' | 'return' — what the median at `pos` measures, from the words with it."""
    window = sent[pos:pos + 70]
    for sep in (";", "]", "\n"):
        cut = window.find(sep)
        if cut >= 0:
            window = window[:cut]
    if _DURATION_RX.search(window) and "%" not in window:
        return "duration"
    # look BEHIND as well: "median drawdown depth of -15.7%" puts the noun before the number, and
    # "the median depth of these drawdowns was -4.2%" puts it after. Both are the same statistic.
    behind = sent[max(0, pos - 40):pos]
    if _DEPTH_RX.search(window) or _DEPTH_RX.search(behind):
        return "depth"
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
                   # THE LIST IS COUNT NOUNS, NOT UNIT NOUNS, and that is the whole principle. Three
                   # gaps were patched one incident at a time before the set was enumerated properly
                   # (2026-07-31: every "<number> <noun>" in every queued draft, ranked by use). The
                   # enumeration settled it — the apparent "gaps" mostly are not:
                   #     months 327   weeks 8   points 32   -> DURATION and MAGNITUDE. "3.6 months"
                   #                                           is not N=3.6. Correctly excluded, the
                   #                                           same reason sessions/days are excluded
                   #                                           from the bare-count branch below.
                   #     times, crises, occurrences        -> genuine counts. Added.
                   # A new noun belongs here only if "<number> <noun>" answers HOW MANY OBSERVATIONS,
                   # never how long or how far. The selftest carries the table.
                   # "events" was ABSENT — the single most common count noun in an event study, so
                   # "Across 166 events, the median recovery is 0.5 months" read as N-missing. Found
                   # 2026-07-31 when the rule was ungated from digest-class and lit up nearly every
                   # honest event-study sentence. Ungating a rule exposes its recall gaps.
                   # WORD-NUMBERS one..ten count too: "across these five events" is correct writing
                   # (the WORD-NUMBER rule only forbids eleven and above), and demanding digits there
                   # would fail the house style for the small-N pieces where N matters most.
                   r"|\b(?:over|across|among)\s+(?:all\s+|these\s+|the\s+){0,2}"
                   r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:\w+\s+){0,2}"
                   r"(?:instances?|episodes?|events?|samples?|cases?|drawdowns?|sessions?|days?)\b"
                   # a bare count noun, but NOT sessions/days: "2544 sessions" is a duration.
                   r"|\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:\w+\s+){0,2}"
                   r"(?:instances?|episodes?|events?|samples?|cases?|drawdowns?|"
                   r"midterms?|elections?|meetings?|cycles?|observations?|"
                   r"times|occurrences?|crises|crisis)\b",
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
    # PRESENT TENSE MATTERS. The list carried only past forms ("triggered", "caused"), so the note
    # "presidential elections regularly TRIGGER market drawdowns" — the exact claim this rule exists to
    # catch — did not even match the pattern. A standing generalisation is stated in the present tense;
    # that is the tense a false causal claim most naturally takes.
    r"\b(?:drives?|drove|driven\s+by|caus(?:e|es|ed|ing)|trigger(?:s|ed|ing)?|spark(?:s|ed|ing)?|"
    r"fuel(?:s|l?ed|ling|ing)?|leads?\s+to|led\s+to|"
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
DIGEST_HEADINGS = ["The mark", "The context", "Similar sessions", "Next session", "Full recovery"]
_SECTION_REQUIRED = [(None, r"(?mi)^\s{0,3}#{1,4}\s*the\s+mark\b"),
                     (None, r"(?mi)^\s{0,3}#{1,4}\s*the\s+context\b"),
                     # Similar sessions (relational content rebuild, item 1) is required exactly when
                     # the evidence carries the analog section — same evidence-driven rule as 3/4, so
                     # a thin-state session that omits SECTION 2A demands no heading for it.
                     ("SECTION 2A", r"(?mi)^\s{0,3}#{1,4}\s*similar\s+sessions\b"),
                     ("SECTION 3", r"(?mi)^\s{0,3}#{1,4}\s*next\s+session\b"),
                     ("SECTION 4", r"(?mi)^\s{0,3}#{1,4}\s*full\s+recovery\b")]
# A draft may end on terminal punctuation, or on terminal punctuation followed by a CLOSED trailing
# parenthetical — "...one episode remains CENSORED. (INDEX-MEASURED; SINGLE-INSTANCE; CENSORED)" is a
# complete note wearing a label tail, not a cut-off generation. Found by the corpus regression when
# TRUNCATED-DRAFT was kind-ungated (2026-08-01): it fired on that note and said "generation was cut
# off" about a draft that finished, while LABEL-FURNITURE was already reporting the real defect —
# the trailing label list — under the right name. A wrong diagnosis is worse than a duplicate.
# The group must be CLOSED, so a genuine truncation inside an open parenthesis still fails, and the
# terminal punctuation is still REQUIRED, so "...the deepest drawdown (INDEX-MEASURED)" with no
# sentence end before it still fails.
_TERMINAL_RX = re.compile(r"[.!?][\"')\]]*\s*(?:\([^()]*\)|\[[^\[\]]*\])?\s*$")


def check_completeness(draft: str, evidence: str, kind: str | None = None) -> list[dict]:
    """-> list of failures. Section presence is driven by the EVIDENCE: a quiet session legitimately has
    no Section 3/4, and demanding them there would be the opposite error.

    TWO DIFFERENT SCOPES live here, and conflating them was the defect:
      TRUNCATED-DRAFT  — KIND-scoped (flagship + note). A study draft cut off mid-generation is
                         broken in every class; it was reachable only through the digest gate, which
                         is the same hole that let a truncated digest score clean in D1 (caught then
                         only by reading the text).
      MISSING/EXTRA-SECTION — EVIDENCE-scoped, digest-only. The section names ARE the digest format.
    """
    out = []
    # RESEARCH CARDS ARE NOT PROSE and must never be truncation-checked: they are machine triage
    # records that legitimately end on a structured verdict line ("— outside the anchor universe").
    # Measured before shipping: a naive ungate fired on 61 non-digest drafts, 60 of them research
    # cards ending exactly that way. Kind-scoping is the difference between a real check and 60
    # false positives. kind=None keeps the old digest-only reach, so the thesis-engine answer path
    # (which has no draft kind and is not a draft) is unaffected.
    if kind in ("flagship", "note") or _digest_class(evidence):
        body = draft.rstrip()
        if body and not _TERMINAL_RX.search(body):
            out.append({"type": "TRUNCATED-DRAFT", "token": "end-of-draft",
                        "detail": "the draft does not end on a complete sentence — generation was "
                                  f"cut off. tail: ...{body[-90:]!r}"})
    if not _digest_class(evidence):
        return out
    # NOTE-FORM drafts (quiet sessions ship as notes — option (b), adopted 2026-07-27): the section
    # contract is a FLAGSHIP contract, and a note has no sections BY DESIGN. Note-form is detected
    # STRUCTURALLY — no markdown headings AND note-sized. That was originally because run_fidelity
    # could not be told the draft kind; it can now (`kind` above), so the rationale has changed even
    # though the code has not: structural detection ALSO covers kind=None callers and a mislabelled
    # record, so it stays as the broader test rather than being narrowed to kind == "note". The size
    # guard is load-bearing: a
    # heading-less FLAGSHIP (the wall-of-text failure) runs hundreds of words and still fails
    # MISSING-SECTION; the note ceiling is 130 words, so 160 leaves margin without opening a hole.
    # TRUNCATED-DRAFT above still applies to notes — a note must end on a sentence too.
    if not re.search(r"(?m)^\s{0,3}#", draft) and len(draft.split()) <= 160:
        return out
    for i, (marker, heading_rx) in enumerate(_SECTION_REQUIRED):
        # marker None -> always required; otherwise required only when the evidence carries that
        # section — and FORBIDDEN when it does not. The first dispersion-led digest of the rebuilt
        # format (2026-07-27 nightly) wrote "## Next session" and "## Full recovery" anyway and
        # padded them with fabricated scaffolding ("was not measured; instead...") plus an invented
        # SURVIVORSHIP claim about it. A section whose evidence is absent can only contain padding
        # or invention; its heading is a hard fail, symmetric with MISSING-SECTION.
        if marker is not None and marker not in evidence:
            if re.search(heading_rx, draft):
                have = DIGEST_HEADINGS[i]
                out.append({"type": "EXTRA-SECTION", "token": have,
                            "detail": f'the draft carries "## {have}" but the evidence has no such '
                                      f"section this session — there is nothing measured to write "
                                      f"there, so the section can only be padding or invention. "
                                      f"Omit the heading and its prose entirely."})
            continue
        if not re.search(heading_rx, draft):
            want = DIGEST_HEADINGS[i]
            out.append({"type": "MISSING-SECTION", "token": want,
                        "detail": f'the draft has no "## {want}" HEADING. The numbers may be present '
                                  f"in running prose — the format is still wrong. The four headings "
                                  f"are verbatim and mandatory: "
                                  + ", ".join(f'"## {h}"' for h in DIGEST_HEADINGS)})
    return out


# Causation asserted BY the piece is the target. Causation the piece QUOTES (the folklore it exists to
# refute) or DENIES (a disclaimer that causes are unknowable) is the opposite of the failure mode, and a
# METHODOLOGICAL "due to" describes why data is absent rather than why a price moved. Measured before
# shipping the unscoped rule: all three published flagships would have failed, and four of six hits were
# one of these three shapes — the drafter is INSTRUCTED to state folklore and to disclaim causality.
_FOLKLORE_RX = re.compile(
    r"\b(?:the\s+)?(?:narrative|folklore|story|conventional\s+wisdom|received\s+wisdom|"
    r"common\s+account|popular\s+account)\b|\b(?:accounts?|commentators?|pundits?|analysts?)\s+"
    r"(?:often\s+)?(?:say|claim|suggest|argue|insist|tell)|\bis\s+said\s+to\b|"
    r"\b(?:often|usually|typically)\s+(?:suggests?|claims?|framed)\b", re.I)
_METHOD_CAUSE_RX = re.compile(
    # "understated/overstated/biased due to ..." is a statement about a NUMBER's limitation — the
    # SURVIVORSHIP label's mandated content — not about why a price moved. Missing from the first
    # list; fired on a compliant pair draft 2026-07-27 ("this number is understated due to
    # SURVIVORSHIP bias"). "due to" stays strict for price claims.
    r"\b(?:not|never|cannot|can'?t|could\s+not|couldn'?t|un(?:available|measured|measurable)|"
    r"excluded?|omitted|censored|incomplete|missing|insufficient|"
    r"understat\w*|overstat\w*|biased)\b[^.]{0,50}\bdue\s+to\b"
    r"|\bdue\s+to\b[^.]{0,50}\b(?:insufficient|incomplete|missing|unavailable|no\s+data|"
    r"observation\s+window|recentness|limited\s+data|sample)\b", re.I)
_CAUSE_DENIED_RX = re.compile(
    r"\b(?:myriad|countless|many|numerous|unknowable|unmeasured|beyond)\b[^.]{0,30}\bfactors?\b"
    # "...driven by factors OUTSIDE this analysis" attributes the cause to something explicitly
    # unmeasured — a disclaimer, the house voice, not an assertion. The adjective-first pattern
    # above missed the postfix form; fired on a compliant pair draft 2026-07-27.
    r"|\bfactors?\s+(?:outside|beyond|not\s+(?:in|measured|captured|covered))\b"
    r"|\bno\s+(?:such\s+)?(?:causal|causation)\b|\bnot\s+(?:a\s+)?caus\w+"
    r"|\bcannot\s+(?:be\s+)?(?:attribut|establish|identif|explain)\w*"
    r"|\bdoes\s+not\s+(?:imply|establish|show|measure)\b[^.]{0,30}\bcaus\w+", re.I)


# HEDGED and DISCLAIMED causation. Measuring the unscoped rule across every historical study draft
# showed the dominant shape is not a false claim but the OPPOSITE: this publication's whole voice is
# discussing the LIMITS of causal inference. "might lead to", "could be due to chance", "impossible to
# ascribe specific causes", "does not address the factors causing these drawdowns", "not a simple
# calendar-driven pattern". Failing those punishes the brand's core move. A hedged modal is not an
# assertion, and a sentence that denies causal knowledge is the reverse of the failure mode.
_HEDGED_CAUSE_RX = re.compile(
    r"\b(?:might|may|could|would|can|possibly|perhaps|potentially|likely|perhaps|seem\w*|appear\w*)\b"
    r"[^.]{0,40}\b(?:caus\w+|driv\w+|trigger\w*|lead\s+to|due\s+to|explain\w*|result\w*)", re.I)
_DISCLAIM_CAUSE_RX = re.compile(
    # ACTIVE forms joined 2026-07-31. The list held only PASSIVES ("cannot BE determined"), so the
    # plainest honest sentence this publication can write — "we cannot say what drove this" — hard
    # FAILED CAUSAL-CLAIM, punishing exactly the voice the rule exists to protect. Widening was
    # previously unsafe because every widening adds shield surface; the preamble guard below closes
    # that, so an active denial followed by named causes is still caught.
    r"\b(?:can(?:not|'?t)|could\s*n[o']t|do(?:es)?\s+not|don'?t|doesn'?t|un(?:able|clear))\s+"
    r"(?:to\s+)?(?:say|tell|know|determine|identify|isolate|disentangle|establish|attribute|ascribe)\b"
    r"|\bwe\s+do\s+not\s+know\b|\bno\s+way\s+to\s+(?:say|tell|know|determine)\b"
    r"|\bimpossible\s+to\b|\bcannot\s+be\s+(?:ascrib|attribut|determin|establish)\w*"
    r"|\bdoes\s+not\s+address\b|\bnot\s+a\s+simple\b|\bcoincidental\b|\bby\s+chance\b"
    r"|\bdue\s+to\s+chance\b|\bnot\s+captured\b|\bunique\s+(?:to|circumstances)\b"
    r"|\blimitations?\s+due\s+to\b|\bselection\s+bias\b|\bSMALL-N\b", re.I)


# THE DISCLAIMER SHIELD (2026-07-31). _CAUSE_DENIED_RX exempted a sentence on the mere PRESENCE of
# denial vocabulary anywhere in it, so a denial that merely PRECEDES named causes bought the whole
# sentence an exemption. It is not a denial then; it is a preamble. Two real instances, one of them
# ALREADY PUBLISHED:
#   "...attributable to factors beyond the scope of this measurement: idiosyncratic company events,
#    changes in investor sentiment, global economic shocks, and shifts in macroeconomic policy."
#   "...driven by factors beyond simple risk-on/risk-off sentiment; company-specific events, broader
#    macroeconomic shifts..., and unexpected geopolitical developments all play a role in shaping
#    sector performance."           <- published, and the exact claim the rule exists to forbid
# The discriminator is whether the sentence goes on to ENUMERATE specific causes after the denial. A
# genuine disclaimer names no causes — that is what makes it a disclaimer:
#   "markets are complex systems driven by myriad factors."                          still exempt
#   "...driven by factors outside this analysis."                                    still exempt
#   "might be entirely coincidental or driven by factors not captured..."            still exempt
# An enumeration is an introducer (colon/semicolon/dash, "such as", "including", "namely") followed by
# a comma, OR two commas plus an "and" — the ordinary shapes of an English list. Deliberately STRICT:
# a false positive costs one redraft, a false negative publishes invented causation, and the second is
# the failure this module exists to prevent.
_CAUSE_ENUM_RX = re.compile(
    r"(?:[:;]|\s[—–-]\s|\bsuch\s+as\b|\bincluding\b|\bnamely\b)[^.]*?,"
    r"|,[^.]*?,[^.]*?\band\b", re.I)


# A list after a denial is not always a list of CAUSES. The house voice enumerates its own LIMITATIONS
# constantly — "limitations due to the SMALL-N size, SURVIVORSHIP bias, and inherent REGIME DEPENDENCE"
# is the honest shape, and the first cut of this guard flagged it. Naming what a measurement cannot
# support is the opposite of asserting a cause, so a tail made of honesty labels and limitation
# vocabulary keeps its exemption. Caught by running the guard over the full queue before shipping it.
_LIMITATION_LIST_RX = re.compile(
    r"\bSMALL-N\b|\bSURVIVORSHIP\b|\bSURVIVOR-SELECTED\b|\bCENSORED\b|\bSECTOR-PROXY\b|"
    r"\bINDEX-MEASURED\b|\bSINGLE-INSTANCE\b|\bNOT-A-(?:SIGNAL|RANKING)\b|\bFORWARD-LOOKING\b|"
    r"\bregime\s+dependen\w*|\bselection\s+bias\b|\bsampl\w+\s+bias\b|\blimitations?\b|"
    r"\bsample\s+size\b|\bobservation\s+window\b", re.I)


def _denial_is_preamble(sentence: str, denial: "re.Match") -> bool:
    """True when the 'denial' is followed, in the same sentence, by an enumeration of named CAUSES."""
    tail = sentence[denial.end():]
    if _LIMITATION_LIST_RX.search(tail):
        return False                      # a list of limitations, not of causes — still a disclaimer
    return bool(_CAUSE_ENUM_RX.search(tail))


def _causal_is_asserted(sentence: str) -> bool:
    """Does THIS sentence ASSERT a cause, rather than quote, hedge, deny, or describe a data limit?"""
    # BOTH denial-family exemptions get the preamble guard, not just the one the live bypass came
    # through. _DISCLAIM_CAUSE_RX is the same shape ("impossible to", "cannot be ascribed", "not
    # captured") and would shield the identical construction through the other door; fixing only the
    # observed instance would leave a known hole. The guard is strictly-stricter, so it cannot create
    # a new false negative. FOLKLORE/METHOD/HEDGED are different shapes and are untouched here — see
    # the exemption-shield audit for their separate assessment.
    denied = _CAUSE_DENIED_RX.search(sentence) or _DISCLAIM_CAUSE_RX.search(sentence)
    if denied and _denial_is_preamble(sentence, denied):
        return True                       # the denial was a preamble; the sentence asserts after it
    return not (_FOLKLORE_RX.search(sentence) or _METHOD_CAUSE_RX.search(sentence)
                or denied or _HEDGED_CAUSE_RX.search(sentence))


# --- RECOVERY GUARANTEE (resilience class, 2026-08-01; ALL classes by the gating lesson) ------------
# The resilience study measures a pre-registered list of events this market recovered from — and a
# market that did NOT recover has no series to measure, so the list's 100% recovery rate is selection,
# not evidence. "Markets always recover" is the sentence that study tempts every draft into writing,
# and the KOSPI attempts established that the model violates present, unambiguous task instructions —
# so this is a CHECKER rule, not a task rule. All classes, not gated on the resilience label: a
# universal-recovery guarantee is a FORWARD-LOOKING promise no evidence block anywhere supports.
_RECOVERY_SUBJ = r"(?:the\s+)?(?:markets?|stocks?|equit(?:y|ies)|indexes|indices|the\s+S&P(?:\s*500)?)"
_RECOVERY_VERB = r"(?:recover\w*|rebound\w*|come\s+back|came\s+back|bounce\w*\s+back|regain\w*|reach\w*\s+new\s+highs?)"
_RECOVERY_GUARANTEE_RX = re.compile(
    rf"{_RECOVERY_SUBJ}\s+(?:(?:has|have|had)\s+)?(?:always|invariably|inevitably|ultimately\s+always|"
    rf"eventually\s+always|without\s+fail)\s+(?:\w+\s+)?{_RECOVERY_VERB}"
    rf"|{_RECOVERY_SUBJ}\s+(?:always|invariably|inevitably)\s+(?:\w+\s+)?{_RECOVERY_VERB}"
    # "every drawdown/crash/decline (has been / is eventually) recovered/erased/regained"
    rf"|\bevery\s+(?:\w+\s+)?(?:drawdowns?|crash(?:es)?|declines?|selloffs?|bear\s+markets?|correction?s?)\b"
    rf"[^.]{{0,50}}\b(?:recover\w*|regain\w*|erased?|reclaim\w*|made\s+whole)"
    # "no drawdown/bear market is/has been permanent"
    rf"|\bno\s+(?:drawdown|bear\s+market|crash|decline|selloff)\s+(?:is|has\s+(?:ever\s+)?been|was)\s+permanent"
    rf"|\b(?:recovery|a\s+rebound)\s+is\s+(?:always\s+)?(?:guaranteed|inevitable|certain|assured)\b", re.I)
# THE HONEST DIRECTION: naming the selection is the entire point of the label, and denying the
# guarantee is the house voice. Both exempt — with the shield closed: an exemption marker followed by
# an ENDORSEMENT ("...and the data proves it") re-asserts the guarantee, and fires.
_RECOVERY_SELECTION_RX = re.compile(
    r"\bby\s+(?:selection|construction)\b|\bsurviv\w+|\bselection\s+effect\b|\bselected\b|"
    r"\bno\s+series\s+to\s+measure\b|\bstill\s+exists?\b|\bdid\s+not\s+(?:survive|reopen|come\s+back)\b", re.I)
_RECOVERY_DENIED_RX = re.compile(
    r"\b(?:not|never|no)\b[^.]{0,40}\b(?:mean|imply|guarantee|prove|show|support|evidence|promise)\w*\b|"
    r"\bcannot\s+(?:be\s+)?(?:conclude|support|guarantee|infer)\w*|\bis\s+not\s+(?:a\s+)?(?:finding|evidence|guarantee)\b|"
    r"\bfolklore\b|\bnarrative\b|\bconventional\s+wisdom\b|\bthe\s+(?:story|myth|adage|saying)\b", re.I)
_RECOVERY_ENDORSE_RX = re.compile(
    r"\b(?:and|but|yet)\b[^.]{0,30}\b(?:prove[sd]?|confirm\w*|bear[s]?\s+(?:it|this|that)\s+out|"
    r"borne\s+out|holds?\s+true|is\s+(?:right|correct|true)|the\s+data\s+agrees?)\b", re.I)


def check_recovery_guarantee(draft: str, evidence: str) -> list[dict]:
    """-> list of failures. A universal 'markets always recover' assertion is a false claim in every
    class: measured history is a sample selected by survival, never a guarantee."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", draft):
        s = sent.strip()
        m = _RECOVERY_GUARANTEE_RX.search(s)
        if not m:
            continue
        exempt = _RECOVERY_SELECTION_RX.search(s) or _RECOVERY_DENIED_RX.search(s)
        if exempt and not _RECOVERY_ENDORSE_RX.search(s[m.end():]):
            continue                      # names the selection or denies the claim, and does not
        out.append({"type": "RECOVERY-GUARANTEE", "token": m.group(0)[:60],
                    "detail": "universal recovery asserted as a finding — the measured list is "
                              "selected by survival (a market that did not recover has no series), "
                              "so a recovery rate is selection, never a guarantee. State the "
                              f"selection effect or drop the claim. sentence: {s[:180]}"})
    return out


def check_causal_claims(draft: str, evidence: str) -> list[dict]:
    """-> list of failures. ALL draft classes, not just the digest: the evidence never measures
    causation in any format, and a note reading "presidential elections regularly TRIGGER market
    drawdowns" is exactly the claim this exists to catch (it passed for months because the rule was
    digest-scoped). Study pieces are held to the same bar, with the three non-assertive shapes above
    excluded so the rule cannot fail a draft for following its own instructions."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", draft):
        s = sent.strip()
        m = _CAUSAL_RX.search(s)
        # The evidence's own NO-CAUSATION instruction contains the very words this rule forbids ("do not
        # write that one caused, drove, triggered..."), so a draft that recites it fires CAUSAL-CLAIM for
        # exactly the wrong reason. Fifth occurrence of this module penalising recited mandatory text —
        # _is_evidence_text existed for it and was wired into the average check only. Reciting the block
        # is still a defect: INSTRUCTION-RECITATION catches it, with the right message.
        # _causal_is_asserted was defined and NOT wired in on the first attempt, so every exclusion was
        # dead and the rule fired on all three shapes it was meant to spare. Caught by testing.
        if m and not _is_evidence_text(s, m, evidence) and _causal_is_asserted(s):
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
    """-> list of failures. Flags prose that reproduces the evidence's INSTRUCTION text verbatim.

    ALL CLASSES since 2026-07-31. It was digest-gated and reported zero hits, which is exactly the
    reading a gated rule gives you either way — the fourth carve-out in this module to hide its own
    coverage rather than a violation. Study evidence carries MORE instruction text than the digest
    does (the DELIBERATELY ABSENT directive, the honesty-label prohibitions, the alignment
    convention), so it is the class with the most to recite."""
    instr_lines = [ln.strip() for ln in evidence.splitlines() if _INSTRUCTION_HINT.search(ln)]
    if not instr_lines:
        return []

    def words(s):
        # DIGITS ARE NOT RECITATION — the module said so in prose and then counted them as words.
        # "2006-11-07, 2010-11-02, 2014-11-04, 2018-11-06, 2022-11-08" normalises to fifteen tokens
        # and cleared the nine-word bar on its own, so a draft QUOTING the event dates (which it is
        # required to do) read as reciting an instruction. Ungating the rule surfaced 42 of these and
        # not one real recitation. Match on the WORDS of an instruction; the figures are the job.
        return [w for w in re.sub(r"[^0-9a-z ]+", " ", s.lower()).split() if not w.isdigit()]

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


# --- SIGN-FLIP INVERSION (pair class, bond-proxy) ---------------------------------------------------
# The one direction-of-claim error that IS deterministically decidable, and it reached review twice
# before this existed: when a pair's evidence carries the sign-FLIP note (the 10Y side is a YIELD-
# change series), a clause asserting what stock and bond PRICES did is pure arithmetic on the stated
# correlation sign — negative yield-basis correlation means prices moved TOGETHER, positive means
# OPPOSITE. A live draft wrote "this negative correlation indicates that stock and bond prices were
# moving in opposite directions" one sentence after correctly reciting the flip rule (2026-07-27,
# rejected factually_wrong). Decidable because: the flag is machine-readable, the claim vocabulary is
# closed, and the truth is sign(-corr). The GENERAL direction-of-claim problem (outperformance,
# index-vs-stock framing, method descriptions) is NOT decidable deterministically and stays a
# review-layer responsibility — the directional flags surface those sentences; they cannot judge them.
# Clause-scoped (";" and sentence enders): the flip-rule statement "bond prices move inversely to
# yields" shares a sentence with the claim but not a clause, and must never itself fire the rule —
# which is why bare "inversely" is deliberately NOT a direction idiom here.
_FLIP_NOTE_RX = re.compile(r"sign-FLIP", re.I)
# The clause used to be required to contain the literal word "price", which made the rule fire on
# PHRASING LUCK: "the two move in opposite directions in price terms" fired, "the two move in opposite
# directions" and "bonds and equities move in opposite directions" did not — same claim, same error.
# Direction-of-claim is the one semantic error established as deterministically decidable and it
# reached review twice before this rule existed, so it may not depend on a word the draft happens to
# use. The clause now qualifies if it names PRICES **or** either side of the pair.
_PRICE_RX = re.compile(r"\bprices?\b", re.I)
_ASSET_SIDE_RX = re.compile(
    r"\bprices?\b|\byields?\b|\bbonds?\b|\btreasur\w+\b|\bequit\w+\b|\bstocks?\b|\bshares?\b|"
    r"\bgold\b|\boil\b|\bcrude\b|\bbitcoin\b|\bBTC\b|\bdollar\b|\bthe\s+two\b|\bboth\b|"
    r"\b(?:SPY|SMH|XL[A-Z]|QQQ|TLT|IEF|DXY|VIX)\b", re.I)
_DIR_OPP_RX = re.compile(r"opposite\s+direction|opposing\s+direction|in\s+opposition|"
                         r"inverse\s+direction", re.I)
_DIR_SAME_RX = re.compile(r"same\s+direction|in\s+tandem|mov(?:ed|ing|e)\s+together|"
                          r"together\s+in\s+the\s+same", re.I)
_CORR_NEG_RX = re.compile(r"negative\s+corr|corr\w*[^.;]{0,40}\bnegative\b|-0?\.\d+", re.I)
_CORR_POS_RX = re.compile(r"positive\s+corr|corr\w*[^.;]{0,40}\bpositive\b", re.I)


_DIR_NEG_RX = re.compile(r"\b(?:not|never|rather\s+than|instead\s+of|no\s+longer|hardly|"
                         r"far\s+from)\s*$", re.I)


def _dir_cue_negated(clause: str, cue_rx: re.Pattern) -> bool:
    """Is this direction cue immediately negated ('...not in tandem', '...rather than together')?"""
    m = cue_rx.search(clause)
    return bool(m and _DIR_NEG_RX.search(clause[max(0, m.start() - 18):m.start()]))


def check_sign_flip_inversion(draft: str, evidence: str) -> list[dict]:
    """-> list of failures. Only when the evidence carries the sign-FLIP note."""
    if not _FLIP_NOTE_RX.search(evidence):
        return []
    out = []
    for clause in re.split(r"[;\n]|(?<=[.!?])\s+", draft):
        if not _ASSET_SIDE_RX.search(clause):
            continue
        opp, same = bool(_DIR_OPP_RX.search(clause)), bool(_DIR_SAME_RX.search(clause))
        if not opp and not same:              # no direction claim at all -> nothing to decide
            continue
        if opp and same:
            # BOTH cues present. This was a blanket skip labelled "unparseable", which is the
            # disclaimer-shield shape again: "prices move in opposite directions, not in tandem"
            # silenced the check by adding the second cue. A NEGATED cue is not a competing claim —
            # strip the negated one and re-read. Only if BOTH survive un-negated is the clause
            # genuinely undecidable, and that is now the narrow skip rather than the broad one.
            opp = opp and not _dir_cue_negated(clause, _DIR_OPP_RX)
            same = same and not _dir_cue_negated(clause, _DIR_SAME_RX)
            if opp == same:
                continue
        neg, pos = bool(_CORR_NEG_RX.search(clause)), bool(_CORR_POS_RX.search(clause))
        if neg == pos:                        # no corr-sign cue in the SAME clause -> not decidable
            continue
        # flip arithmetic: yield-basis negative => prices SAME direction; positive => OPPOSITE
        wrong = (neg and opp) or (pos and same)
        if wrong:
            stated = "negative" if neg else "positive"
            claimed = "opposite directions" if opp else "the same direction"
            correct = "the same direction" if neg else "opposite directions"
            out.append({"type": "SIGN-FLIP-INVERSION", "token": f"{stated} corr -> {claimed}",
                        "detail": f"the evidence's sign-FLIP note means a {stated} yield-basis "
                                  f"correlation puts stock and bond PRICES in {correct} — the draft "
                                  f"claims {claimed}, the reverse of the measurement. "
                                  f"clause: {clause.strip()[:160]}"})
    return out


# --- IDENTIFIER LEAKAGE (all classes) ---------------------------------------------------------------
# Internal identifiers are never reader-appropriate: "Bitcoin (ANCHOR_BTC)" and "the rapid bounce
# following calm_2013_2017" reached PENDING drafts (2026-07-27 review pass) because nothing checked
# for them. ANCHOR_* is always a leak. Episode keys are a leak when UNQUOTED — the reviewer's own
# bar: the RATE_10Y/SPY edit removed ANCHOR_* but left quoted episode keys ("calm_2013_2017") as
# tolerated styling, so a quoted key passes and a bare one in running prose fails.
_ANCHOR_LEAK_RX = re.compile(r"\bANCHOR_[A-Za-z0-9_]+")
_EPISODE_KEY_RX = re.compile(r"(?<![\"“‘'])\b[a-z]+_\d{4}(?:_\d{4}|Q\d)?\b")


def check_identifier_leak(draft: str) -> list[dict]:
    """-> list of failures. Evidence-independent: these tokens are never publishable prose."""
    out = []
    for m in _ANCHOR_LEAK_RX.finditer(draft):
        ctx = draft[max(0, m.start() - 40):m.end() + 30].replace("\n", " ")
        out.append({"type": "IDENTIFIER-LEAK", "token": m.group(0),
                    "detail": f"raw internal identifier in prose — use the readable name the "
                              f"evidence provides. ctx: {ctx}"})
    for m in _EPISODE_KEY_RX.finditer(draft):
        ctx = draft[max(0, m.start() - 40):m.end() + 30].replace("\n", " ")
        out.append({"type": "IDENTIFIER-LEAK", "token": m.group(0),
                    "detail": f"unquoted episode key in prose — say it in English ('the 2008 crash', "
                              f"'the 2022 repricing') or quote the engine's window name. ctx: {ctx}"})
    return out


# --- LABEL FURNITURE (all classes) ------------------------------------------------------------------
# Naming ONE label inline is accepted style ("remains CENSORED"). TWO OR MORE canonical uppercase
# label terms in the SAME sentence is a pasted checklist, not writing — "INDEX-MEASURED (drawdowns
# are shallower...), SMALL-N (anecdotes only...), FORWARD-LOOKING (...)" closed a pending note as
# terminal furniture (2026-07-27 review pass). Case-SENSITIVE on the canonical uppercase forms, so
# honest lowercase prose ("a single instance", "the survivor-only panel") can never trip it.
_LABEL_TERM_RX = re.compile(
    r"\b(?:SMALL-N|LARGE-N|INDEX-MEASURED|FORWARD-LOOKING|SECTOR-PROXY|SINGLE[- ]INSTANCE|"
    r"CENSORED|SURVIVORSHIP|SURVIVOR-SELECTED|NOT-A-SIGNAL|NOT-A-RANKING|PROXY)\b")


def check_label_furniture(draft: str) -> list[dict]:
    """-> list of failures. A sentence carrying >= 2 canonical uppercase label terms is furniture."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", draft):
        hits = _LABEL_TERM_RX.findall(sent)
        if len(hits) >= 2:
            out.append({"type": "LABEL-FURNITURE", "token": " + ".join(hits[:4]),
                        "detail": "two or more label terms pasted into one sentence — a checklist, "
                                  "not writing. State each caveat in its own words where it belongs. "
                                  f"sentence: {sent.strip()[:160]}"})
    return out


# --- WORD-NUMBERS (digest class) --------------------------------------------------------------------
# The digest's NUMBERS rule has always said figures are DIGITS copied verbatim; this makes it a hard
# fail instead of a hope. Forced by a persistent fabrication: 8 of 9 live drafts of the rebuilt digest
# verbalised the analog-set size as "fifteen" (analogs/sessions/most-closely-resembled — the noun
# varies, so noun-adjacent extraction cannot chase it). A spelled-out number of this size in a digest
# is either a conversion of an evidence digit (barred) or an invention (worse); honest small-word
# idioms ("one of these", "two crises") are untouched because the list starts at eleven. Scoped to
# digest-class evidence, same as the median rules — study essays are a different register and were
# not measured for this rule.
_BIG_WORD_NUM_RX = re.compile(
    r"\b(?:eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)\b", re.I)


def check_word_numbers(draft: str, evidence: str) -> list[dict]:
    """-> list of failures. NO draft may spell out numbers eleven and above.

    Ungated from digest-class 2026-07-31 alongside check_median_discipline. A spelled-out number is a
    conversion or an invention whichever class it appears in — the live KOSPI draft wrote "Eleven such
    drawdowns have occurred" where the evidence prints 11, and nothing caught it."""
    out = []
    for m in _BIG_WORD_NUM_RX.finditer(draft):
        ctx = draft[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")
        out.append({"type": "WORD-NUMBER", "token": m.group(0),
                    "detail": "digest figures are DIGITS copied verbatim from the evidence — a "
                              "spelled-out number is a conversion or an invention. Write the "
                              f"evidence's digit form or omit the count. ctx: {ctx}"})
    return out


# BARE-AVERAGE had NO denial exemption while CAUSAL-CLAIM had five, so a sentence ARGUING AGAINST
# averaging failed a rule about REPORTING averages — the sharpest form of the carve-out pattern, and
# found in two published pieces:
#   "reflecting an underlying tension that isn't captured by simple averages"
#   "This number alone does not tell the full story; it's an average across various market conditions"
# Both are the house voice doing its job. The exemption reuses the item-1 preamble guard so it cannot
# become a shield: a denial that precedes an actually-reported average still fires.
_AVG_DENIED_RX = re.compile(
    r"\b(?:not|never|isn'?t|aren'?t|doesn'?t|don'?t|cannot|can'?t|no)\b[^.]{0,40}"
    r"\b(?:captur\w+|tell\w*|show\w*|reflect\w*|conve\w+|substitut\w*|replac\w*|suffic\w*)\b"
    r"|\b(?:more\s+than|beyond|behind|underneath|obscur\w+|hid\w+|mask\w+|conceal\w+|"
    r"flatten\w*|destroy\w*|wash\w+\s+out)\b"
    r"|\bnot\s+(?:an?\s+)?(?:average|mean)\b|\bavoid\w*\s+(?:the\s+)?(?:average|mean)\b", re.I)
# A reported average looks like a NUMBER attached to the word, or an explicit "the average was/is".
_AVG_REPORTED_RX = re.compile(
    r"(?:average|mean)[^.]{0,30}?-?\d+(?:\.\d+)?|-?\d+(?:\.\d+)?[^.]{0,30}?(?:average|mean)"
    r"|\b(?:the\s+)?(?:average|mean)\s+(?:was|is|of|stood|came|sits|runs)\b", re.I)


def _average_is_reported(sentence: str, m: "re.Match") -> bool:
    """Does the sentence REPORT an average, or argue against relying on one?"""
    if _AVG_REPORTED_RX.search(sentence):
        return True                      # a figure is attached: reported, whatever else it says
    denial = _AVG_DENIED_RX.search(sentence)
    if denial and not _denial_is_preamble(sentence, denial):
        return False                     # criticising averaging, and naming nothing after it
    return True


def check_median_discipline(draft: str, evidence: str, kind: str | None = None) -> list[dict]:
    """-> list of failures. Sentence-scoped: the hit rate and N must sit in the SAME sentence as the
    median, because a reader takes the number from the sentence they are reading, not from a paragraph
    three sentences down.

    ALL CLASSES since 2026-07-31. This was digest-gated, and recovery/pair/event evidence is not
    digest-class — so the module's signature rule had never run on a study piece. A recovery median
    without its N ("the median recovery stands at 7.2 months", N unstated) is precisely the misleading
    statistic this publication exists to refuse, and the study classes need the rule MORE than the
    digest does, not less. Third instance of the digest gate acting as a shield; CAUSAL-CLAIM was
    ungated for the same reason ("it passed for months because the rule was digest-scoped").

    SCOPE VARIES BY KIND, and the split was measured before it was built. Across the 12 published
    pieces the rule newly failed:
      FLAGSHIPS put the range beside the median and the N a paragraph away — N was present in the
        piece in all three. A reader of 800 words has the denominator.
      NOTES put N beside the median and omitted the range from the entire piece — 0 of 6 carried it
        anywhere. Their gap is a MISSING statistic, not a distant one, so piece scope would clear
        none of them and sentence scope costs them nothing they had.
    So a flagship may satisfy N-and-range anywhere in the piece; a note must satisfy them in the
    sentence, because in a note the sentence very nearly IS the piece. Default is the STRICT reading:
    a caller that does not know the kind gets sentence scope."""
    piece_scoped = (kind == "flagship")
    piece_n = bool(_N_RX.search(draft)) if piece_scoped else False
    piece_range = bool(_RANGE_RX.search(draft)) if piece_scoped else False
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", draft):
        s = sent.strip()
        if not s:
            continue
        if _median_is_reported(s):
            m = re.search(r"\bmedian\b", s, re.I)
            mkind = _median_kind(s, m.end()) if m else "return"
            has_n = bool(_N_RX.search(s)) or piece_n
            has_range = bool(_RANGE_RX.search(s)) or piece_range
            where = "the piece" if piece_scoped else "the same sentence"
            if mkind in ("duration", "depth"):
                if not (has_n and has_range):
                    out.append({"type": "MEDIAN-WITHOUT-N", "token": f"median ({mkind})",
                                "detail": f"a median {mkind} must carry its N and its range in "
                                          f"{where} (a hit rate does not exist for a "
                                          f"{mkind}). sentence: {s[:180]}"})
            elif not (_HITRATE_RX.search(s) and has_n):
                out.append({"type": "MEDIAN-WITHOUT-N", "token": "median (return)",
                            "detail": f"a median return must carry its hit rate AND N in {where} "
                                      f"— a bare median reads as a forecast. sentence: {s[:180]}"})
        m = _AVERAGE_RX.search(s)
        if m and not _is_evidence_text(s, m, evidence) and _average_is_reported(s, m):
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
    # "survivor" would also match "survivor-selected" — the lookahead keeps the two claims distinct
    # so a draft honestly carrying SURVIVOR-SELECTED cannot be failed for inventing SURVIVORSHIP.
    "SURVIVORSHIP": r"survivor(?![\s-]selected)",
    "SURVIVOR-SELECTED": r"\bsurvivor[\s-]selected\b",
    "SINGLE-INSTANCE": r"\bsingle[\s-]instance\b|\bn\s*=\s*1\b",
    "CENSORED": r"\bcensored\b",
    "INDEX-MEASURED": r"\bindex[\s-]measured\b",
    "DISTRIBUTION": r"\blarge[\s-]*n\b",
    "FORWARD-LOOKING": r"\bforward[\s-]looking\b",
    "SECTOR-PROXY": r"\bsector[\s-]proxy\b",
    "NOT-A-SIGNAL": r"\bnot[\s-]a[\s-]signal\b",
    "NOT-A-RANKING": r"\bnot[\s-]a[\s-]ranking\b",
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


def run_fidelity(draft: str, evidence: str, kind: str | None = None) -> dict:
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
        # EVERY mention, not just the first. Checking only the first is the disclaimer-shield shape
        # in a third rule: "this is not a SURVIVORSHIP problem; SURVIVORSHIP bias makes the number
        # understated" negated the opening mention and asserted freely afterwards, and the whole
        # label was exempted on the strength of the denial. The label is invented if ANY mention
        # asserts it; a draft that only ever denies it keeps the exemption it is due.
        m = next((mm for mm in re.finditer(claim_rx, draft, re.I)
                  if not _label_mention_is_negated(draft, mm)), None)
        if not m:
            continue
        labels[name]["invented"] = True
        failures.append({"type": "INVENTED-LABEL", "token": name,
                         "detail": f"draft asserts {name} but the evidence never carries it — "
                                   f"a false caveat is a false claim, same class as a false number"})

    failures.extend(check_median_discipline(draft, evidence, kind))
    failures.extend(check_word_numbers(draft, evidence))
    failures.extend(check_identifier_leak(draft))
    failures.extend(check_label_furniture(draft))
    failures.extend(check_sign_flip_inversion(draft, evidence))
    failures.extend(check_causal_claims(draft, evidence))
    failures.extend(check_recovery_guarantee(draft, evidence))
    failures.extend(check_completeness(draft, evidence, kind))
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
