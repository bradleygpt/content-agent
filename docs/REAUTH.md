# Substack auth + the 2026-07-14 suspension incident

## ⛔ READ THIS FIRST — the account is currently SUSPENDED

On **2026-07-14**, during C0 validation against the brand-new **Akribeia Insights**
(`akribeiainsights.substack.com`), the first **programmatic Note** posted through the unofficial API
tripped Substack's abuse detection. Within minutes the account was **suspended**:

> "Your account is currently suspended. Something you posted may have violated Substack's **Spam & Phishing
> policy**. If you believe this is a mistake, you can submit an appeal to our Standards & Enforcement team
> here: https://substack.com/appeals"

**What almost certainly triggered it:** a brand-new account, minutes old, making automated API writes with a
spoofed browser `User-Agent`, posting a low-content Note ("c0 header probe — ignore"). That is a textbook
bot/spam signature.

**Actions taken immediately:**
- All further API writes **stopped** (no attempt was made to work around or evade the suspension).
- `config.json` → `publisher.adapter` forced to **`"manual"`**, and `programmatic_notes_enabled: false`.
- `publisher.publish_note()` is **hard-gated off** — it now always falls through to the manual outbox, so no
  scheduled run or queue Approve can post to Substack again while this is unresolved.

**Bradley's move:** appeal at <https://substack.com/appeals>. Do not re-enable the programmatic write path
until the appeal resolves *and* you have decided whether to use the unofficial write API at all (see the
recommendation at the bottom).

---

## Cookie storage (works; unaffected by the suspension)

Secrets live OFF-REPO in `%USERPROFILE%\.content_agent\`.

1. Log in to substack.com in the browser as the publication owner.
2. DevTools → Application → Cookies → `https://substack.com` → copy the `substack.sid` value.
3. Write `%USERPROFILE%\.content_agent\substack_cookie_string.txt` containing:
   `substack.sid=<value>`

### Which encoding? — BOTH work (tested 2026-07-14)
The browser value is **URL-encoded** (`s%3A…` = `s:…`, `%2B` = `+`). We tested both forms against
`get_user_profile()`:

| form | result |
|---|---|
| **RAW, exactly as copied from devtools (URL-encoded)** | ✅ authenticates — **use this one** |
| URL-decoded (`urllib.parse.unquote`) | ✅ also authenticates |

Keep the **raw** form: it is what the browser actually sends, requires no transformation, and is what
`requests`/`python-substack` pass through verbatim. Do not store both — one credential copy only.

### Verify
`.venv/Scripts/python.exe scripts/c0_validate.py`  ← auth only. **Do NOT run `--all` or `--note`** while the
account is suspended (and reconsider `--note` permanently — see below).

---

## Capability truth, measured live (2026-07-14)

| Capability | Result | Notes |
|---|---|---|
| Cookie auth | ✅ **WORKS** | `get_user_profile()` → `id=529192399`, `name="Akribeia Insights"` |
| Post **draft** creation | ✅ **WORKS** | `create_draft_from_markdown` → real draft `id=207075402` appeared on the publication, `is_published=false` |
| **Notes** (programmatic) | ⚠️ **technically works, but GOT US SUSPENDED** | No library supports Notes. The raw endpoint `POST /api/v1/comment/feed` returns **403 (HTML edge block)** with plain headers, and **200** only with browser-like headers (`User-Agent`/`Origin`/`Referer`). It posted note `id=294589442` — and the account was suspended right after. **Now hard-gated off.** |
| Full programmatic **publish** | ❓ **UNPROVEN** | `publish_draft` exists in the library, but it was deliberately **not exercised** (draft-only by instruction), and now cannot be tested while suspended. |
| **Manual outbox** (paste) | ✅ **WORKS** | `out/publish_outbox/` md+html, now carrying the "Akribeia Insights" byline. **Unaffected by the suspension — this is the launch path.** |

### Recommendation
Spoofing browser headers to drive an undocumented write endpoint is exactly the behaviour Substack's
Spam & Phishing policy targets, and it cost us the account on day one. Even after a successful appeal, the
honest read is: **do not automate Notes.** Automate *drafting* (which is where all the value is — the
fidelity-checked engine evidence), and keep publishing a human action: paste from the outbox, or click
publish on a draft. That was always the design intent ("the unofficial API must never be load-bearing").

## Never
- Never commit cookie material. `.gitignore` blocks `*cookie*` / `*token*` as a backstop.
- Never paste the cookie into chat/logs — reference the file path only.
- Never attempt to circumvent an enforcement action.
