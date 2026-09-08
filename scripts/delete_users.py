"""
Delete one or more users from Supabase Auth (auth.users), by email.

Uses the service-role admin client (app.services.supabase.supabase_service.admin)
already configured for this project — same credentials the API server uses.

Usage (from repo root):
    python scripts/delete_users.py user@example.com
    python scripts/delete_users.py user1@example.com user2@example.com
    python scripts/delete_users.py --file emails.txt      # one email per line
    python scripts/delete_users.py user@example.com --dry-run   # preview, delete nothing
    python scripts/delete_users.py user@example.com --yes       # skip confirmation prompt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for `app.*` imports

from app.services.supabase import supabase_service  # noqa: E402


def load_emails(args: argparse.Namespace) -> list[str]:
    emails = list(args.emails)
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
        emails += [line.strip() for line in text.splitlines() if line.strip()]
    seen = set()
    deduped = []
    for e in emails:
        key = e.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    return deduped


def find_users_by_email(emails: list[str]) -> dict[str, object]:
    """Returns {email_lower: user_object} for every match found, via one list_users() scan."""
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
    parser.add_argument("emails", nargs="*", help="Email address(es) to delete")
    parser.add_argument("--file", help="Path to a text file with one email per line")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted, delete nothing")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    args = parser.parse_args()

    emails = load_emails(args)
    if not emails:
        parser.error("No emails given — pass them as arguments or via --file")

    print(f"Looking up {len(emails)} email(s)...")
    found = find_users_by_email(emails)

    for email in emails:
        u = found.get(email.lower())
        if u:
            print(f"  [found]   {email}  (id={u.id}, created_at={u.created_at})")
        else:
            print(f"  [missing] {email}  (no matching account)")

    if not found:
        print("Nothing to delete.")
        return

    if args.dry_run:
        print(f"\n--dry-run: would delete {len(found)} account(s). No changes made.")
        return

    if not args.yes:
        reply = input(f"\nPermanently delete {len(found)} account(s)? This cannot be undone. [y/N] ")
        if reply.strip().lower() != "y":
            print("Aborted.")
            return

    for email, u in found.items():
        supabase_service.admin.auth.admin.delete_user(u.id)
        print(f"  Deleted {email}")

    print(f"\nDone. Deleted {len(found)} account(s).")


if __name__ == "__main__":
    main()
