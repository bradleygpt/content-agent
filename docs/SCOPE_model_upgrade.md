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
