# What the saved files can prove: each model's artefacts exist and
# agree with the register, and what Mark I actually decided in 2025.
import fernhill
from ballast import governance as gv
from ballast.config import AS_OF, ROOT

con = fernhill.connect()
inv = gv.load_inventory()
checks = gv.check_artefacts(inv, ROOT)
clean = [c["id"] for c in checks if not c["problems"]]
print(f"{len(clean)} of {len(checks)} models: files found, "
      f"nothing to report")
for c in checks:
    for p in c["problems"]:
        print(f"  {c['id']:<6}{p}")

rows = con.execute("""
    SELECT product, count(*) AS apps,
           count(*) FILTER (WHERE decline_reason
                            = 'score_below_cutoff') AS score_declines,
           min(cutoff) AS cutoff
    FROM applications
    WHERE year(app_date) = ? AND mark1_score IS NOT NULL
    GROUP BY product ORDER BY product""", [AS_OF.year]).fetchall()
print(f"\nMark I in {AS_OF.year}: applications scored and cut off")
print(f"{'product':<10}{'apps':>8}{'score declines':>16}{'cut-off':>9}")
for p, n, d, c in rows:
    print(f"{p:<10}{n:>8,}{d:>16,}{c:>9}")
mk1 = next(e for e in inv if e["id"] == "MK1")
print(f"register: {mk1['purpose']}")
