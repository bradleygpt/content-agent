# DATA.md — what is excluded from this repo and where it lives

| Excluded | Location | Why |
|---|---|---|
| Substack session cookie | `%USERPROFILE%\.content_agent\substack_cookie_string.txt` or `substack_cookies.json` | secret; re-auth per docs/REAUTH.md |
| Review-queue state (drafts, streak, autonomy state) | `queue/` + `state/` | runtime data; regenerable/operational |
| Publish outbox (rendered md/html for paste) | `out/publish_outbox/` | generated output |
| Logs | `logs/` | operational |
| Python venv | `.venv/` | rebuild: `python -m venv .venv; pip install -r requirements.txt` |

Source-of-truth inputs are NOT copied into this repo: markets-llm artifacts are read in place
(`C:/Users/bmhar/code/markets-llm/deliverables/...`) — this project is a read-only consumer.
