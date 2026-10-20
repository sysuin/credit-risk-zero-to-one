# The agency's letters in Fernhill's records: who is rated, how the
# letters are spread, how often they move, and how they line up with
# Fernhill's own grades and with distance to default.
import fernhill
from ballast import market as mk

con = fernhill.connect()
LETTERS = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]

n_rated, n_listed, first = con.execute("""
    SELECT count(DISTINCT r.company_id),
           (SELECT count(*) FROM companies WHERE listed),
           min(r.rating_date)
    FROM ratings r WHERE agency_rating IS NOT NULL""").fetchone()
print(f"rated by the agency: {n_rated} of {n_listed} listed clients")
print(f"  quarterly from {first:%b %Y}")

dist = dict(con.execute("""
    SELECT agency_rating, count(*) FROM ratings
    WHERE agency_rating IS NOT NULL GROUP BY 1""").fetchall())
total = sum(dist.values())
print("\nquarter-end ratings by letter")
print("  " + "".join(f"{x:>8}" for x in LETTERS))
print("  " + "".join(f"{dist.get(x, 0) / total:>8.1%}"
                     for x in LETTERS))

moved, pairs = con.execute("""
    WITH q AS (
        SELECT agency_rating AS now, lag(agency_rating) OVER (
            PARTITION BY company_id ORDER BY rating_date) AS before
        FROM ratings WHERE agency_rating IS NOT NULL)
    SELECT count(*) FILTER (WHERE now <> before), count(before)
    FROM q""").fetchone()
print(f"\nquarters in which the letter changed: {moved} of {pairs}"
      f" ({moved / pairs:.1%})")

rows = con.execute("""
    SELECT CASE WHEN i.internal_grade <= 3 THEN '1-3'
                WHEN i.internal_grade <= 6 THEN '4-6'
                ELSE '7-10' END AS band,
           a.agency_rating, count(*)
    FROM ratings a JOIN ratings i
      ON i.company_id = a.company_id
     AND i.rating_date = a.rating_date
     AND i.internal_grade IS NOT NULL
    WHERE a.agency_rating IS NOT NULL
    GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
table = {}
for band, letter, n in rows:
    table.setdefault(band, {})[letter] = n
print("\nat the March review: Fernhill's grade against the agency's")
print(f"  {'grade':<7}" + "".join(f"{x:>7}" for x in LETTERS))
for band in ("1-3", "4-6", "7-10"):
    print(f"  {band:<7}" + "".join(
        f"{table[band].get(x, 0):>7}" for x in LETTERS))

# The letter against the market: distance to default at quarter ends.

p = mk.grade_in_force(con, mk.merton_panel(con))
quarter = p.month.map(lambda m: m.month % 3 == 0)
q = p[p.agency_rating.notna() & quarter]
q = q.assign(notch=q.agency_rating.map(LETTERS.index))
rho_dd = q[["notch", "dd"]].corr(method="spearman").iloc[0, 1]
g = q[q.internal_grade.notna()]
rho_g = g[["notch", "internal_grade"]].corr(
    method="spearman").iloc[0, 1]
print(f"\nquarter ends with a letter and a DD: {len(q):,}")
print(f"  rank correlation of the letter with DD {rho_dd:+.2f}, "
      f"with the grade {rho_g:+.2f}")
print("  median DD by letter")
print(f"  {'':<7}" + "".join(f"{x:>7}" for x in LETTERS))
print(f"  {'DD':<7}" + "".join(
    f"{q[q.agency_rating == x].dd.median():>7.1f}" for x in LETTERS))
