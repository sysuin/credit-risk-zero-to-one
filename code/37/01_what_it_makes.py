# What the simulator writes: its seed, and the rows in every table.
import json

import fernhill
from ballast.config import FERNHILL

manifest = json.loads((FERNHILL / "manifest.json").read_text())
print(f"seed {manifest['seed']}")
tables = manifest["tables"]
book = fernhill.connect()
for name, n in tables.items():
    have = book.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    assert have == n, name
names = list(tables)
half = (len(names) + 1) // 2
print(f"loan book: {len(names)} tables, as the manifest lists them")
for left, right in zip(names[:half], names[half:] + [""]):
    r = f"{right:<21}{tables[right]:>10,}" if right else ""
    print(f"  {left:<21}{tables[left]:>10,}   {r}")
truth = fernhill.connect(truth=True)
rows = truth.execute("""
    SELECT table_name, estimated_size FROM duckdb_tables()
    ORDER BY table_name""").fetchall()
print(f"truth: {len(rows)} tables")
for name, _ in rows:
    n = truth.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    print(f"  {name:<21}{n:>10,}")
booked, shadow = truth.execute("""
    SELECT count(*) FILTER (WHERE NOT shadow),
           count(*) FILTER (WHERE shadow)
    FROM origination""").fetchone()
print(f"origination: {booked:,} booked, {shadow:,} shadow accounts")
