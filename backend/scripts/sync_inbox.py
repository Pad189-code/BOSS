"""
Synchronise la boîte mail IMAP (Gmail test) → table email_requests.

Usage:
  cd backend
  python -m scripts.sync_inbox
  python -m scripts.sync_inbox --test
"""

from __future__ import annotations

import argparse
import asyncio
import json

from app.services.email_ingestion import sync_inbox, test_imap_connection


async def main(test_only: bool) -> None:
    if test_only:
        result = await test_imap_connection()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    result = await sync_inbox()
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Tester la connexion IMAP seulement")
    args = parser.parse_args()
    asyncio.run(main(args.test))
