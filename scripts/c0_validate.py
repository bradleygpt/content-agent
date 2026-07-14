"""C0 validation harness — run the moment the session cookie exists (see docs/REAUTH.md).

Validates against the REAL publication, in order, stopping with honest capability truth:
  (a) auth works with the stored cookie
  (b) create a Note programmatically (raw endpoint — no library support exists for Notes)
  (c) create a flagship POST as a DRAFT (library path), and report whether full programmatic
      publish is available (it is in the library; --publish actually exercises it on the test draft)

  .venv/Scripts/python.exe scripts/c0_validate.py [--note] [--draft] [--publish] [--all]

Default (no flags) runs auth only. Every step prints the true result; nothing is deleted automatically —
inspect the publication afterwards and clean up the test artifacts by hand.
"""
from __future__ import annotations
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from content_agent.publisher import (SubstackCookieAdapter, COOKIES_JSON, COOKIE_STRING)  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--note", action="store_true")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--publish", action="store_true", help="ALSO publish the test draft (visible!)")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    print(f"cookie file present: json={COOKIES_JSON.exists()} string={COOKIE_STRING.exists()}")
    if not (COOKIES_JSON.exists() or COOKIE_STRING.exists()):
        print("BLOCKED: no cookie stored. Follow docs/REAUTH.md, then re-run.")
        sys.exit(2)

    ad = SubstackCookieAdapter()
    print("\n(a) AUTH:", "OK" if ad.auth_ok() else "FAILED — cookie invalid/expired (docs/REAUTH.md)")
    if not ad.auth_ok():
        sys.exit(1)

    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    if args.note or args.all:
        r = ad.publish_note(f"[c0 validation note {stamp}] measured evidence in a world of confident "
                            "noise — test post, ignore.")
        print(f"(b) NOTE: mode={r['mode']} ok={r['ok']} detail={r['detail']}")
    if args.draft or args.publish or args.all:
        r = ad.publish_post(title=f"[c0 validation draft {stamp}]",
                            subtitle="test draft — ignore",
                            markdown="This is a C0 validation draft. It should appear in the publication's "
                                     "drafts list. Delete after confirming.",
                            draft_only=not args.publish)
        print(f"(c) POST: mode={r['mode']} ok={r['ok']} detail={r['detail']}")
    print("\nRecord the capability truth in README (C0 results table) after this run.")


if __name__ == "__main__":
    main()
