# Exercise 2: a lower materiality threshold, $50 and 0.5% of the
# balance, applied to the whole decade under the 2021 definition.
import fernhill
from ballast import performance as perf

con = fernhill.connect()
for cents, share in ((10_000, 0.01), (5_000, 0.005)):
    perf.MATERIAL_CENTS, perf.MATERIAL_SHARE = cents, share
    imm = con.execute("""
        SELECT count(*) FROM performance p
        JOIN (SELECT account_id, min(month) AS m FROM performance
              WHERE missed >= 3 GROUP BY 1) f
          ON f.account_id = p.account_id AND f.m = p.month
        WHERE NOT (p.arrears_cents > ? AND
                   p.arrears_cents > ? * p.balance_cents)""",
                      [cents, share]).fetchone()[0]
    eps = perf.default_episodes(con, "dod2021", stitched=False)
    print(f"${cents / 100:.0f} and {share:.1%}: immaterial at first "
          f"90 dpd {imm:,}")
    print(f"  episodes {len(eps):,} on {eps.account_id.nunique():,} "
          f"accounts")
