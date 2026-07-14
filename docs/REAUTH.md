# Substack re-auth procedure (cookies rotate eventually)

All secrets live OFF-REPO in `%USERPROFILE%\.content_agent\` (gitignored patterns as backstop).

## One-time / whenever auth fails (c0_validate.py step (a) FAILED)

1. Log in to substack.com in the browser as the publication owner.
2. Open DevTools → Application → Cookies → `https://substack.com`.
3. Copy the cookie header. Two accepted storage formats (either works):
   - **String form** — create `%USERPROFILE%\.content_agent\substack_cookie_string.txt` containing the
     semicolon-separated cookies (at minimum `substack.sid=...`; copying the whole cookie line is fine).
   - **JSON form** — `%USERPROFILE%\.content_agent\substack_cookies.json` in python-substack
     `export_cookies` format: `[{"name": "substack.sid", "value": "...", ...}, ...]`.
4. Validate: `.venv/Scripts/python.exe scripts/c0_validate.py` (auth only; add `--all` to exercise
   Note + draft creation against the real publication).

Session cookies historically stay valid for months. When any publish call starts failing, the adapters
degrade automatically to the manual outbox (`out/publish_outbox/`) — nothing is lost; re-auth at leisure.

## Never

- Never commit cookie material, even temporarily. `.gitignore` blocks `*cookie*` / `*token*` as a backstop.
- Never paste the cookie into chat/logs. The file path is the only thing that should ever be referenced.
