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

# names/idioms containing digits that are NOT data (stripped before extraction, both sides)
_STRIP_PATTERNS = [r"s\s*&\s*p\s*500", r"sp500", r"s&p500", r"nasdaq[\s-]?100", r"russell[\s-]?2000",
                   r"\b10-?k\b", r"\b10-?q\b", r"\b2s10s\b", r"\b10y\b", r"\bcovid-19\b", r"\b60/40\b",
                   r"\b24/7\b", r"\b401\(k\)\b"]
_WORD_NUMS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
              "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
              "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20}
_UNIT_RX = [
    ("pct", r"%|percent(?:age)?(?:\s+points?)?|per\s+cent"),
    ("month", r"months?\b|mo\b"),
    ("week", r"weeks?\b|wks?\b"),
    ("day", r"days?\b"),
    ("year", r"years?\b|yrs?\b"),
    ("count", r"events?\b|meetings?\b|midterms?\b|elections?\b|episodes?\b|cases?\b|instances?\b|"
              r"drawdowns?\b|anecdotes?\b|stocks?\b|names?\b|(?:data\s+)?points?\b|occurrences?\b|"
              r"cycles?\b|samples?\b"),
    ("corr", r"corr(?:elation)?s?\b"),
]
_DATE_RX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# lookahead permits unit-fused forms ("14.0mo", "3.6-month"); digits/dots after are still barred so we
# never split "0.5" out of "0.51"
_NUM_RX = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\d.])")


def _prep(text: str) -> str:
    t = text.replace("−", "-").replace("–", "-")
    t = re.sub(r"(?<=\d)\.\.(?=[\d-])", " to ", t)         # "0.5..14.0" range syntax -> "0.5 to 14.0"
    t = re.sub(r"(?m)^(\s*)\d+[.)]\s+", r"\1", t)          # markdown ordered-list markers are not data
    for p in _STRIP_PATTERNS:
        t = re.sub(p, " ", t, flags=re.I)
    return t


def _unit_for(t: str, start: int, end: int, after: int) -> str | None:
    """AFTER-FIRST, clause-bounded unit resolution: units overwhelmingly trail their numbers ("-24.5%",
    "14.0mo", "range 0.5 to 14.0 months"); the before-window is a fallback for prefix forms ("corr 0.17").
    The after-window is cut at the clause boundary (';' or newline) so a '%' from the previous clause never
    captures the next clause's number."""
    clause = t[end:end + after]
    cut = min([i for i in (clause.find(";"), clause.find("\n")) if i >= 0] or [len(clause)])
    wa = clause[:cut]
    best, best_d = None, 10 ** 9
    for unit, rx in _UNIT_RX:
        m = re.search(rx, wa, re.I)
        if m and m.start() < best_d:
            best, best_d = unit, m.start()
    if best:
        return best
    wb = t[max(0, start - 25):start]
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
            wb = t[max(0, m.start() - 45):m.start()]
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
    "CENSORED": (r"(?m)^\s*CENSORED: |\[CENSORED",
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
}

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
}

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
        if u and (v, u) in ev_pairs:
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
        if labels[name]["required"] or not re.search(claim_rx, draft, re.I):
            continue
        labels[name]["invented"] = True
        failures.append({"type": "INVENTED-LABEL", "token": name,
                         "detail": f"draft asserts {name} but the evidence never carries it — "
                                   f"a false caveat is a false claim, same class as a false number"})

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
        bound = all((tk["unit"] and (tk["value"], tk["unit"]) in ev_pairs)
                    or (not tk["unit"] and (tk["value"] in ev_values or tk["value"] in ev_years))
                    for tk in s_tokens)
        directional.append({"sentence": sent.strip()[:300], "numbers_bound": bound})

    return {"passed": not failures, "failures": failures, "labels": labels,
            "numeric": numeric, "directional": directional}
