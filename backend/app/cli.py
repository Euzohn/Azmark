"""Command line entry points (spec #78).

Usage (from ``backend/``):

    python -m app create-admin --username admin --email admin@example.com

The password is read interactively unless ``--password`` is given.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from app.core.db import SessionLocal
from app.services.admin import AdminBootstrapError, ensure_admin


def _prompt_password() -> str | None:
    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        return None
    if len(password) < 6:
        print("Password must be at least 6 characters.", file=sys.stderr)
        return None
    return password


def _create_admin(args: argparse.Namespace) -> int:
    password = args.password
    if password is None:
        password = _prompt_password()
        if password is None:
            return 1

    with SessionLocal() as db:
        try:
            user, outcome = ensure_admin(
                db,
                username=args.username,
                email=args.email,
                password=password,
                reset_password=args.reset_password,
            )
        except AdminBootstrapError as exc:
            print(f"Could not create admin: {exc}", file=sys.stderr)
            return 1

    messages = {
        "created": "Admin created",
        "promoted": "Existing account promoted to admin",
        "updated": "Admin updated",
        "exists": "Admin already exists (password unchanged)",
    }
    print(f"{messages[outcome]}: {user.username} ({user.email or 'no email'})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-admin", help="Create or promote an admin user")
    create.add_argument("--username", required=True)
    create.add_argument("--email")
    create.add_argument("--password")
    create.add_argument(
        "--reset-password",
        action="store_true",
        help="Reset the password of an existing account",
    )

    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return _create_admin(args)
    return 1
