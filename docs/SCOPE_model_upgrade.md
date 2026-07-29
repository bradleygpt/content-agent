# Scope: drafting-model candidates in the 8GB budget. REPORT ONLY — nothing downloaded.

2026-07-28. Current: gemma3:12b-it-q4_K_M (Mar 2025), ~6.1-6.2 GiB resident at num_ctx 8192 on the
8,151 MiB shared card. The measured failure profile that motivates the question: fabrication under
thin evidence (the quiet shape), number verbalisation ("fifteen" for 150), directional inversion
(the sign flip), identifier leakage (ANCHOR_*/episode keys in prose), label recitation. The job is
FAITHFUL TRANSCRIPTION of a structured argument, not creative writing — candidates are judged on
instruction-following and faithfulness reputation, not benchmark totals.

## Candidates that fit the budget (quantized, ollama-servable, released since gemma3:12b)

| model | released | Q4 footprint | fit at 8k ctx | why it's on the list |
|---|---|---|---|---|
| **qwen3.5:9b** | Mar 2026 | ~5.5-6 GB | comfortable | the strongest post-gemma3 release in-budget; instruction-following reputation edges gemma-class peers; thinking mode is OFF-able (mandatory for us — reasoning verbosity is anti-transcription) |
| **gemma4:12b** | ~Feb 2026 | ~6.6 GB Q4_K_M | same envelope as today | direct successor, same family = lowest prompt-migration risk; reported better text quality at the same footprint |
| **qwen3:8b** | Apr 2025 | ~5.2 GB | comfortable | the conservative fallback: mature, well-characterised instruction-following, smallest migration risk after gemma4 |
| gemma3:12b-it-**qat** | Apr 2025 | ~6-6.5 GB | same | not an upgrade — the SAME model with quantization-aware training, recovering Q4 quality; cheapest possible test of "is quantization part of our fabrication problem" |

Excluded, with reasons: phi4:14b (~9 GB Q4 — over budget with context), mistral-small 22-24B
(~14 GB), llama 3.3 70B / llama 4 MoE (not in class), deepseek-r1 distills (reasoning-tuned =
verbose chain-of-thought pressure, the opposite of faithful transcription), sub-5B models
(phi4-mini, qwen3:4b, llama3.2:3b — capability floor risk on the flagship shapes; the 4B era is
what the 12B replaced). Qwen 3.6 27B exists but is far over budget.

Co-tenancy: all four candidates fit alongside the existing yield-and-retry discipline; none change
the philosophy-llm 4B co-tenant math. Disk: ~6-7 GB per pull.

## A/B design (frozen before any pull)

- **Evidence**: the three frozen blocks already banked — quiet digest (2026-07-27, the 0/8 baseline
  session), crossing digest (2026-07-24, the shape that passes today), pair note (BTC-gold, the
  class the nightly passed unattended).
- **N**: 6 first attempts per SHAPE per model (18/model), no retry, no queue writes. (The handoff
  said "N=6 per model (the three shapes)"; 2 per shape cannot rank four models — 6 per shape is the
  minimum that can. Flagging the deviation rather than silently making it.)
- **Scoring**, two layers:
  1. MECHANICAL: first-attempt fidelity pass rate per shape, plus per-class failure counts from the
     checker (WORD-NUMBER, NO-MATCH, EXTRA-SECTION, SIGN-FLIP-INVERSION, MISSING/INVENTED-LABEL,
     CAUSAL-CLAIM, recitation).
  2. REVIEW-LAYER, tallied by grep + hand: identifier leakage (ANCHOR_*/episode-key regex —
     mechanical), label-recitation furniture (bracketed label lists — mechanical), directional
     inversion outside the pair case (hand), and MUSH — defined for scoring as "no sentence makes a
     claim beyond restating a single statistic" (judgment, scored blind to which model produced it).
- **Baseline**: gemma3:12b runs the same 18 as arm zero, same session, so the comparison is
  same-day, same-GPU, same-checker.
- **Decision rule (proposed, to freeze at approval)**: a challenger must beat gemma3's mechanical
  pass rate on EVERY shape (no trading the crossing shape for the quiet one) and produce no new
  review-layer failure class. Ties break toward gemma4 (migration risk), then qwen3.5 (headroom).
- **Cost**: ~4 models x 18 drafts x ~2-3 min ≈ 3-4 GPU-hours, schedulable off-nightly. Pulls ~25 GB
  disk total, deletable after.

## Side-benefit noted while designing the scoring

Identifier leakage and label-recitation furniture are grep-decidable and appear in the CURRENT
model's output (three of six pending notes). They could become checker rules for the existing
pipeline independent of any model change — cheaper than a model swap and worth doing first, since
the A/B would then score all models under the same, stricter gate.

Sources: [WhatLLM 2026 rankings](https://whatllm.org/best-ollama-models),
[LocalLLM 8GB benchmarks](https://localllm.in/blog/best-local-llms-8gb-vram-2025),
[PromptQuorum model updates](https://www.promptquorum.com/local-llms/local-llm-model-updates-2026),
[Gemma4 12B vs Qwen3.5 9B](https://www.betterclaw.io/blog/gemma-4-12b-vs-qwen-3-5-9b),
[Gemma 4 12B VRAM](https://techsy.io/en/blog/gemma-4-12b),
[Gemma 4 vs Qwen 3.5 benchmarks](https://gemma4all.com/blog/gemma-4-vs-qwen-3-5-benchmarks).

## A/B RESULT (2026-07-29; N=6 first attempts per shape per model, no retries, frozen blocks)

| model | crossing | quiet | pair | review-layer (blind-judged, then unblinded) |
|---|---|---|---|---|
| gemma3:12b-q4_K_M (baseline) | 0/6 | 5/6 | 0/6 | count-fabrication x5 ("fifteen") |
| **gemma4:12b** (think off) | **1/6** | **6/6** | 0/6 | mush x2 (vacuous year-lists); count-fabrication **0** |
| qwen3.5:9b (think off) | 0/6 | 5/6 | 0/6 | count-fabrication x1; messiest crossing failure spread |
| qwen3:8b (think off) | 0/6 | 4/6 | 0/6 | template-stub deferral x8; 5 truncations |
| gemma3:12b-qat | 0/6 | 4/6 | 0/6 | count-fabrication x5 — same tic, same rate |

Notes recorded with the table:
- gemma4's first arm ran with thinking ON by default and produced 18/18 empty bodies (the budget
  went to the thinking channel) — a post-cutoff discovery; the arm was purged and rerun think-off.
- **QUANTIZATION EXONERATED**: QAT (same weights, better quant) reproduces the "fifteen" fabrication
  at the baseline's rate and passes nothing more. The tic is the weights, not the quant — the
  ranking is clean.
- **THE PAIR COLUMN IS EVIDENCE-CAUSED**: every arm failed pair 0/6 on IDENTIFIER-LEAK — every
  model copies the tension line's unquoted `covid_2020` into prose. Quoting/humanising the episode
  key in the builder's tension line would likely lift the pair column for ALL models; it was not
  changed mid-A/B (identical evidence per arm is the design).
- **THE TENSION RULE KILLED MUSH BY CONSTRUCTION**: 0 mush in 30 pair drafts across all arms —
  every draft led with the claim. The only mush anywhere was gemma4's 2 vacuous every-year lists
  on the quiet shape.

DECISION-RULE VERDICT (frozen rule: beat baseline on EVERY shape, no new review-layer class):
**no arm clears.** gemma4 beats on crossing (1>0) and quiet (6>5), ties 0/6 on the evidence-broken
pair shape, and introduced the 2 vacuous-list mush instances. It is, however, the only model on
which the A/B's motivating failure (number verbalisation) is ABSENT — 0 instances against the
baseline's 5-6 per run.

RECOMMENDED NEXT STEP (not adoption): fix the tension line's episode-key quoting evidence-side,
then rerun ONLY the pair shape (6 drafts x gemma3 + gemma4). If gemma4 then beats on all three, the
frozen rule is met on remeasured evidence and the swap question goes to Bradley with a clean table.
The swap is Bradley's call, not this table's. All five models remain on disk pending the decision.

## PAIR-SHAPE RERUNS (2026-07-29, evidence-side causes removed stepwise) + FINAL VERDICT

| evidence state | gemma3 pair | gemma4 pair | leak class remaining |
|---|---|---|---|
| original (bare episode keys + raw ANCHOR_ header) | 0/6 | 0/6 | both |
| round 2: episode keys quoted (_epq, all builders) | 1/6 | 0/6 | ANCHOR_ header copied 5/6 by BOTH models |
| round 3: + readable names in the header (_adisp) | **5/6** | 3/6 | none for gemma3; gemma4's own furniture x3 |

**FINAL VERDICT (frozen rule, remeasured evidence): gemma4 does NOT clear — the incumbent stays.**
gemma4 wins crossing (1/6 vs 0/6) and quiet (6/6 vs 5/6) but loses the remeasured pair shape
(3/6 vs 5/6) on its own label-furniture habit, not on evidence artifacts. No swap.

The A/B's largest finding was never about models: the pair column was ~85% EVIDENCE-caused.
gemma3 went 0/6 -> 5/6 with zero model changes — the evidence was handing every model raw
identifiers as the only available names. Two structural fixes shipped from this (episode-key
quoting + readable header names, emission-audited in the selftest), and they lift PRODUCTION, not
just the benchmark. The residual model signatures are real and documented: gemma3 verbalises
numbers on the crossing shape (0/6 first-attempt, retry-dependent — the standing weak spot);
gemma4 pastes label furniture and pads thin evidence with vacuous lists; quantization remains
exonerated. Challenger models stay on disk; re-opening the swap question requires a new
measurement, not a re-read of this one.
