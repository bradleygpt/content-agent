# DECISION 0001 — Manual publish is the launch policy; programmatic Notes are retired

**Status:** accepted (Bradley, 2026-07-15). **Supersedes:** the incident-session protective hack, which is
now deliberate, documented policy.

## What happened

On **2026-07-14**, during the first live C0 validation of the brand-new **Akribeia Insights**
(`akribeiainsights.substack.com`), the harness posted one **programmatic Note** through the unofficial
endpoint (`POST /api/v1/comment/feed`, reachable only by spoofing browser `User-Agent`/`Origin`/`Referer`
headers). Within minutes Substack **suspended the account** for a **Spam & Phishing** policy violation. A
brand-new account making automated, browser-spoofed writes to an undocumented endpoint is a textbook bot
signature.

Measured before the suspension: cookie auth worked; **draft creation worked** (a real draft, `id=207075402`,
landed unpublished — a quiet non-publishing write that drew **no** enforcement); the Note post is the single
action that triggered the ban.

## The policy

1. **Launch publish mode = manual outbox.** `publisher.adapter = "manual"`. Every approved piece renders to
   `out/publish_outbox/` (markdown + HTML, Akribeia Insights byline) for Bradley to paste. The unofficial
   API is never load-bearing — the original design intent, now enforced by config.

2. **Programmatic Notes = retired, permanently.** `programmatic_notes_enabled = false`, and
   `publisher.publish_note()` is hard-gated to fall through to the outbox. This is **not** "until further
   notice" — automating Notes via a spoofed-header write to an undocumented endpoint is exactly the behaviour
   that policy targets, and it is off the table for good, appeal outcome notwithstanding.

3. **Programmatic DRAFT creation = allowed in principle, OFF for now.**
   `programmatic_draft_creation_allowed = false`. Draft creation is a quiet, non-publishing write that
   behaved cleanly and drew no enforcement, so it remains a legitimate *future* convenience (create the
   draft via the API; Bradley clicks publish). It stays disabled for launch — the outbox/paste path is
   simpler and provably safe.

## Conditions to revisit (draft creation ONLY — never Notes)

All of the following must hold before `programmatic_draft_creation_allowed` (and `adapter="auto"`) may be
reconsidered:
- the suspension appeal (<https://substack.com/appeals>) has **resolved in our favour** and the account is
  in good standing;
- a deliberate decision is made (not a default) that a non-publishing draft write is worth the
  unofficial-API fragility;
- it is introduced **gradually** — a single manual draft creation, observed for a day, before any automated
  use — from an **established** account, not a fresh one.

Notes automation is **not** on this list and never will be.

## Enforcement in code

- `config/config.json` → `publisher`: `adapter="manual"`, `programmatic_notes_enabled=false`,
  `programmatic_draft_creation_allowed=false`, with the policy summary inline.
- `content_agent/publisher.py` → `publish_note()` hard-gated off; `publish_post()` id extraction fixed
  (`draft_id_from_response`).
- `scripts/c0_validate.py` → live modes blocked behind an explicit override flag; the default/`--selftest`
  path is fixture-only and never touches Substack; the `--note` path is a no-op that states the retirement.
- `docs/REAUTH.md` → the full incident record and the both-cookie-encodings finding.
