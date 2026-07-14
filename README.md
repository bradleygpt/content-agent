# content-agent

Turns the markets-llm ecosystem's **measured analysis** into publishable content: *measured evidence in a
world of confident noise*. Every piece is built on one study the engine actually computed, structured as a
weighted two-sided case, with every honesty label carried (SMALL-N, SECTOR-PROXY, CENSORED, INDEX-MEASURED,
SURVIVORSHIP, DISTRIBUTION). It never makes calls, never predicts, never drops a caveat for punch —
deferral language is the brand, not hedging.

**Read-only consumer of markets-llm** (artifacts, run outputs, event registry) — never writes to it.
Zero-cost throughout. X/Twitter is Phase 2 — no X surface exists here.

## Layout

- `content_agent/publisher.py` — swappable publish adapters (Substack cookie API / manual paste outbox)
- `content_agent/studies.py` — the artifact library (reads markets-llm, read-only)
- `content_agent/triggers.py` — calendar (event registry), notable-results scan, weekly cadence
- `content_agent/news.py` — RSS topicality hints (framing only, never claims)
- `content_agent/drafter.py` — gemma3:12b drafting (flagship + notes), mission voice, provenance
- `content_agent/fidelity.py` — THE FIDELITY CHECKER (deterministic build-blocker; see below)
- `content_agent/queue_store.py` + `server.py` + `static/drafts.html` — phone review queue
- `run_daily.py` — the daily pass (GPU-lowest-priority; yields to everything)
- `scripts/c0_validate.py` — Substack capability validation harness

## C0 capability truth — MEASURED LIVE 2026-07-14 (⛔ account suspended)

**Publication:** Akribeia Insights — akribeiainsights.substack.com

| Capability | Status |
|---|---|
| Cookie auth | ✅ **WORKS** (`id=529192399`, name "Akribeia Insights") |
| Post **draft** creation | ✅ **WORKS** — real draft `id=207075402` landed, unpublished |
| **Notes** (programmatic) | ⚠️ works only with spoofed browser headers — **and it got the account SUSPENDED** (Spam & Phishing). Now **hard-gated off**. |
| Full programmatic **publish** | ❓ **UNPROVEN** — `publish_draft` exists but was deliberately not exercised, and can't be tested while suspended |
| **Manual outbox** (paste) | ✅ **WORKS**, carries the Akribeia Insights byline — **unaffected; this is the launch path** |

**LAUNCH MODE: outbox / manual paste.** `publisher.adapter` is forced to `"manual"` and
`programmatic_notes_enabled: false` until the appeal (https://substack.com/appeals) resolves and a decision
is made on whether to use the unofficial write API at all. See `docs/REAUTH.md` for the full incident.

The value of this project was never the posting — it is the fidelity-checked drafting. Drafting is
unaffected and fully operational.

## The fidelity checker (hard precondition)

Runs before any draft reaches the queue. Deterministic:
1. **Numeric binding** — every numeric token in the draft must match a number in the cited evidence
   INCLUDING ITS UNIT ("2.5 months" evidence vs "2.5 weeks" draft = HARD FAIL). Formatting normalized
   (−4.2% / -4.2 percent / "six weeks"), nothing looser.
2. **Label completeness** — every honesty label in the source evidence block must appear in the draft.
3. **Directional-claim flagging** — engine attribution + directional verb sentences are surfaced to the
   reviewer with their numeric-bind status (not auto-failed).
Hard fail → one regeneration with violations injected → second fail lands in the queue as FAILED-FIDELITY
(never silently dropped, never publishable in that state).

## Autonomy flag

Ships **OFF**. Flip criteria are encoded in `config/config.json` + `queue_store.py`, not vibes:
≥12 consecutive approvals with zero correctness edits (taste edits don't count; correctness edits reset),
fidelity checker operational the whole streak. Tripwire: any post-publication factual correction
auto-reverts the flag. Streak state is visible in the queue UI.

## Runbook

- Queue server: `.venv/Scripts/python.exe -m content_agent.server` (127.0.0.1:8799; reached from the phone
  via markets-llm's authenticated tunnel at `/drafts`).
- Daily pass: `.venv/Scripts/python.exe run_daily.py` (scheduled; exits quietly if GPU busy).
- Re-auth: `docs/REAUTH.md`. Data exclusions: `DATA.md`.
