#!/usr/bin/env python3
"""Print one checksum per table, so two runs of the generator can be compared."""
import duckdb

from ballast.config import LOANBOOK, TRUTH

for path in (LOANBOOK, TRUTH):
    con = duckdb.connect(str(path), read_only=True, config={"threads": 1})
    for (name,) in con.execute("SELECT table_name FROM information_schema.tables ORDER BY 1").fetchall():
        n, h = con.execute(f"SELECT count(*), sum(hash(t)) FROM {name} t").fetchone()
        print(f"{path.stem:<9} {name:<22} {n:>9} {h}")
