# Every table in Fernhill's loan book, counted against the manifest.
import json

import fernhill
from ballast.config import FERNHILL

con = fernhill.connect()
manifest = json.loads((FERNHILL / "manifest.json").read_text())
expected = manifest["tables"]

found = con.execute("""
    SELECT table_name, count(*) AS columns
    FROM information_schema.columns
    GROUP BY ALL ORDER BY table_name""").fetchall()

rows = []
for name, columns in found:
    (n,) = con.execute(f"SELECT count(*) FROM {name}").fetchone()
    rows.append((name, columns, n))

half = (len(rows) + 1) // 2
print(f"{'table':<21}{'cols':>4}{'rows':>9}  "
      f"{'table':<17}{'cols':>4}{'rows':>10}")
for left, right in zip(rows[:half], rows[half:] + [None]):
    line = f"{left[0]:<21}{left[1]:>4}{left[2]:>9,}  "
    if right:
        line += f"{right[0]:<17}{right[1]:>4}{right[2]:>10,}"
    print(line.rstrip())

agree = sum(expected.get(name) == n for name, _, n in rows)
print(f"{len(rows)} tables; {agree} agree with the manifest "
      f"(seed {manifest['seed']})")
