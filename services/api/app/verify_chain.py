"""Command-line chain check: `make verify` (or python -m app.verify_chain). Exit code 1 if broken."""

import sys

from app.core.eventlog import verify_chain
from app.db import get_engine


def main() -> int:
    with get_engine().connect() as c:
        r = verify_chain(c)
    if r["ok"]:
        print(f"✓ {r['count']:,} events verified · head #{r['head_seq']} {r['head_hash'][:16]}…")
        return 0
    print(f"✗ chain broken at #{r['broken_at']}: {r['problem']} ({r['count']:,} events verified before it)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
