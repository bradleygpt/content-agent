"""C0 validation harness.

⛔ SUBSTACK IS OFF-LIMITS (account suspended 2026-07-14; appeal pending). Do NOT run any live mode
(`--auth`/`--note`/`--draft`/`--publish`/`--all`) — they touch substack.com. They are retained only so the
harness is ready if/when access is deliberately restored. Programmatic Notes are RETIRED permanently
(policy: docs/DECISIONS/0001-manual-publish-policy.md) and cannot be re-enabled from here.

The safe, always-runnable mode is:

  .venv/Scripts/python.exe scripts/c0_validate.py --selftest

which validates the harness itself (the draft-id extraction bug) against a CANNED response fixture — no
network, no cookie, no Substack. This is what CI/regression should run.

Live modes (do not use while suspended): [--auth] [--note] [--draft] [--publish] [--all].
"""
from __future__ import annotations
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from content_agent.publisher import (SubstackCookieAdapter, COOKIES_JSON,  # noqa: E402
                                     COOKIE_STRING, draft_id_from_response)

# Canned response shapes for the fixture test. The FIRST is python-substack's real
# create_draft_from_markdown return (the id is nested under "draft") — the exact shape that made the old
# harness print "draft id None" on 2026-07-14 while draft 207075402 actually landed.
_FIXTURES = [
    # (label, response, expected_id)
    ("library shape (id nested under 'draft') — the 2026-07-14 incident case",
     {"draft": {"id": 207075402, "draft_title": "x", "is_published": False},
      "tags": None, "prepublish": None, "publish": None}, 207075402),
    ("legacy/top-level id shape", {"id": 999, "draft_title": "y"}, 999),
    ("draft present but id None -> fall back to top-level", {"draft": {"id": None}, "id": 42}, 42),
    ("empty / None / junk -> None", {}, None),
    ("None response -> None", None, None),
    ("non-dict -> None", "oops", None),
]


def selftest() -> int:
    print("C0 HARNESS SELF-TEST (fixture-only; no Substack) — draft_id_from_response")
    ok = 0
    for label, res, expected in _FIXTURES:
        got = draft_id_from_response(res)
        good = got == expected
        ok += good
        print(f"  {'OK ' if good else 'XX '} got={got!r:>12}  want={expected!r:>12}  {label}")
    passed = ok == len(_FIXTURES)
    print(f"\nSELF-TEST: {ok}/{len(_FIXTURES)} {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def _live_blocked():
    print("BLOCKED: live Substack modes are disabled — the account is suspended (2026-07-14) and Substack is "
          "off-limits until the appeal resolves. Run `--selftest` for the fixture-only harness check.")
    return 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="fixture-only harness validation (SAFE)")
    ap.add_argument("--auth", action="store_true")
    ap.add_argument("--note", action="store_true")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--i-understand-substack-is-suspended", action="store_true",
                    help="required override to attempt any live mode (do not use)")
    args = ap.parse_args()

    if args.selftest or not any(vars(args).values()):
        sys.exit(selftest())

    if not args.__dict__["i_understand_substack_is_suspended"]:
        sys.exit(_live_blocked())

    # --- live path (guarded; retained for post-appeal use only) ---
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
        print("(b) NOTE: SKIPPED — programmatic Notes are permanently retired (policy). Never re-enable.")
    if args.draft or args.publish or args.all:
        r = ad.publish_post(title=f"[c0 validation draft {stamp}]", subtitle="test draft — ignore",
                            markdown="C0 validation draft. Delete after confirming.",
                            draft_only=not args.publish)
        print(f"(c) POST: mode={r['mode']} ok={r['ok']} detail={r['detail']}")


if __name__ == "__main__":
    main()
