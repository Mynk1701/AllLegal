"""
Set a user's billing tier by email — used to comp our internal testers.

Uses the service-role admin client (app.services.supabase.supabase_service) — the
same credentials the API server uses. Looks up the auth user by email, then upserts
their `profiles.tier`.

Usage (from repo root):
    python scripts/set_tier.py tester@example.com internal
    python scripts/set_tier.py user@example.com free
    python scripts/set_tier.py a@x.com b@y.com internal          # multiple emails, one tier
    python scripts/set_tier.py --file emails.txt internal        # one email per line
    python scripts/set_tier.py tester@example.com internal --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for `app.*` imports

from app.services.supabase import supabase_service  # noqa: E402

VALID_TIERS = {"free", "pro", "internal"}


def load_emails(emails: list[str], file: str | None) -> list[str]:
    all_emails = list(emails)
    if file:
        text = Path(file).read_text(encoding="utf-8")
        all_emails += [line.strip() for line in text.splitlines() if line.strip()]
    seen, deduped = set(), []
    for e in all_emails:
        if e.lower() not in seen:
            seen.add(e.lower())
            deduped.append(e)
    return deduped


def find_users_by_email(emails: list[str]) -> dict[str, object]:
    """Returns {email_lower: user_object} for every match, via one list_users() scan."""
    targets = {e.lower() for e in emails}
    resp = supabase_service.admin.auth.admin.list_users()
    users = resp if isinstance(resp, list) else getattr(resp, "users", resp)
    found = {}
    for u in users:
        email = getattr(u, "email", None)
        if email and email.lower() in targets:
            found[email.lower()] = u
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("args", nargs="+", help="One or more emails followed by the tier (free|pro|internal)")
    parser.add_argument("--file", help="Path to a text file with one email per line")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change, change nothing")
    ns = parser.parse_args()

    *emails_pos, tier = ns.args
    tier = tier.lower()
    if tier not in VALID_TIERS:
        parser.error(f"Last argument must be the tier, one of {sorted(VALID_TIERS)} (got {tier!r})")

    emails = load_emails(emails_pos, ns.file)
    if not emails:
        parser.error("No emails given — pass them before the tier, or via --file")

    print(f"Looking up {len(emails)} email(s)...")
    found = find_users_by_email(emails)

    for email in emails:
        u = found.get(email.lower())
        print(f"  [{'found' if u else 'missing'}] {email}" + (f"  (id={u.id})" if u else ""))

    if not found:
        print("Nothing to update.")
        return

    if ns.dry_run:
        print(f"\n--dry-run: would set {len(found)} account(s) to tier '{tier}'. No changes made.")
        return

    ok = 0
    for email, u in found.items():
        if supabase_service.set_tier(u.id, tier):
            ok += 1
            print(f"  Set {email} -> {tier}")
        else:
            print(f"  FAILED {email}")

    print(f"\nDone. Updated {ok}/{len(found)} account(s) to '{tier}'.")


if __name__ == "__main__":
    main()
