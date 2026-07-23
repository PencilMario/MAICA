"""Minimal LanceDB persistence probe for Python and Nuitka builds."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import lancedb


async def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: lancedb_nuitka_probe.py DATABASE_PATH")

    db_path = Path(sys.argv[1]).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = lancedb.connect(str(db_path))
    if "probe" not in (db.list_tables().tables or []):
        db.create_table(
            "probe",
            data=[
                {"id": "a", "user_id": -1, "raw_text": "alpha", "vector": [1.0, 0.0, 0.0, 0.0]},
                {"id": "b", "user_id": 7, "raw_text": "private", "vector": [0.0, 1.0, 0.0, 0.0]},
            ],
        )
    table = db.open_table("probe")
    rows = table.search([1.0, 0.0, 0.0, 0.0], query_type="vector").where("user_id = -1").limit(1).to_list()
    if not rows or rows[0]["raw_text"] != "alpha":
        raise AssertionError(f"unexpected search result: {rows!r}")
    print("LANCEDB_PROBE_OK")


if __name__ == "__main__":
    asyncio.run(main())
