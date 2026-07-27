# Scope: the quiet-shape drafting failure — options, evidence, costs. REPORT ONLY, nothing built.

2026-07-27. The dispersion-led (no-crossing) digest shape went 0-for-4 tonight with worsening
hallucination (final round: 20 failures), while the crossing shape passed cleanly the same day on
the same machinery (session 2026-07-24). Every fabrication was caught mechanically — the checker is
not the problem. This is a drafting-capability signature on ONE shape, and the mechanism is visible
in the failures themselves: the quiet evidence block gives the model far less concrete material to
transcribe, and gemma3:12b-it-q4_K_M fills thin evidence with crossing-digest furniture — fabricated
Next-session/Full-recovery scaffolding, habit labels (SURVIVORSHIP/CENSORED) from the crossing
shape, verbalised numbers in padding prose.

## The measured baseline (tonight, all against the same frozen 2026-07-27 evidence)

| round | failures | classes |
|---|---|---|
| nightly 0de1bd | 3 | fabricated sections + invented label + duration median |
| 7fe440 | 9 | invented labels ×2, WORD-NUMBER ×3, more |
| 88d37c | ~5 | dispersion furniture again |
| 41bde1 | 20 | wholesale hallucinated figures |

Crossing-shape same day: passed in 1 run (2 attempts) once the evidence block was sound.

## Option (a) — shape-specific quiet task: shorter, more prescriptive. RECOMMENDED FIRST.

A second DIGEST_TASK variant selected when the evidence has no SECTION 3 (the same mechanical
routing law PAIR_TASK uses): three headings only (The mark / The context / Similar sessions),
~250-300 word target with a hard 400 ceiling, and an explicit license that a quiet digest is
SUPPOSED to be short — the padding pressure is the invention pressure. The word budget is the lever:
tonight's quiet drafts ran 550-700 words against ~300 words of actual evidence content.

- Cost: LOW. One task string + routing branch + selftests. No checker surface changes.
- Measurable: A/B against tonight's frozen evidence — N=4 generations under the new task vs
  tonight's 0/4 baseline, same session data, count passes and failure classes. Measure before
  adopting, per the standing rule.

## Option (b) — quiet sessions ship as a NOTE, not a flagship-length piece.

The strongest evidence tonight is that NOTES PASS: the nightly's autonomous BTC-gold notes went 2
for 3 on first exposure to a brand-new evidence class, because the 40-130-word single-stat format
leaves no room to invent. A quiet session's real content — the dispersion line, the named analogs,
the 5-session aggregate — is genuinely note-sized. `_run_digest` would branch on `lead`:
crossing -> flagship digest, dispersion -> digest-note.

- Cost: MODERATE. NOTE_TASK needs the analog rules (dates verbatim, no synthesised aggregates);
  the median/word-number/causal checks are already class-wide. New selftests.
- The real question is EDITORIAL, not technical: on a quiet day, is the digest a short flagship or
  a note? D0's law was "variable depth, never variable honesty" — a note is the variable-depth
  answer taken seriously. But it changes the product's daily identity, which is Bradley's call,
  not an engineering default.

## Option (c) — model capability. LAST RESORT, agreed.

The drafting model is gemma3:12b-it-q4_K_M (8,151 MiB card, shared three ways). A larger or
higher-precision model collides with zero-cost and with the GPU capacity wall (hardware, not
software — see memory). Not proposed. A cheaper variant worth noting for completeness: a LOWER
temperature for the quiet shape only (currently 0.7 for all drafting) — less entropy where there is
less material. Nearly free to test in the same A/B as (a).

## Recommendation

Run (a)'s A/B first — with the temperature variant as a second arm — because it preserves the
format identity and costs an hour. Adopt only what the A/B clears. If neither arm clears, (b) is
the honest fallback and goes to Bradley as a product decision. Nothing is built until the scope is
approved and the A/B is measured.

## A/B RESULT (2026-07-27, run same evening; pre-registered bar >= 3/4 first-attempt passes)

| arm | passes | verdict | failure profile |
|---|---|---|---|
| baseline (full task, t0.7) | 0/8 | — | 3-20 failures/draft; fabricated sections, invented labels, word-numbers |
| A1: short task, t0.7 | 2/4 | does not clear | 0-4 failures/draft; 1× CAUSAL-CLAIM, 1× NO-MATCH cluster |
| A2: short task, t0.4 | 1/4 | does not clear | 0-3 failures; lower temp did NOT help (one truncation) |

**Neither arm cleared; the routing was removed per the frozen rule.** The measurement itself is
informative: the word-budget hypothesis is confirmed (failures collapsed an order of magnitude,
drafts landed 312-368 words), but 50% first-attempt is not a shape that ships on this model.
Context, not adoption: under the production one-retry mechanism, A1's ~50% per attempt implies
roughly 75% per run — still below the crossing shape's demonstrated reliability.

**ESCALATED TO BRADLEY — option (b), the product question:** should quiet sessions ship as a NOTE
("flagship on crossing days, note on quiet days")? The strongest evidence in favour is the nightly's
own unattended 2-for-3 note pass rate on a brand-new evidence class, and the reviewer's input on
record: that identity is "defensible, not a demotion." Until decided, quiet sessions simply do not
ship a digest — the format's designed honest outcome. DIGEST_TASK_QUIET remains in drafter.py,
unrouted, as the measured artifact.
