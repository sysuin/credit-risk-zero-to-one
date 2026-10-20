# Three things the truth's definitions and the market feed imply.
import fernhill
from ballast.config import TRUTH

con = fernhill.connect()
con.execute(f"ATTACH '{TRUTH}' AS truth (READ_ONLY)")
one = lambda sql: con.execute(sql).fetchone()  # noqa: E731

rows, accts, twice = one("""
    WITH k AS (SELECT account_id, month, count(*) n FROM truth.pd12
               GROUP BY ALL)
    SELECT sum(n), count(DISTINCT account_id),
           count(*) FILTER (WHERE n > 1) FROM k""")
print(f"truth.pd12: {rows:,} rows on {accts:,} accounts;")
print(f"  {twice:,} account-months appear twice (opening, month end)")

n, bk, never = one("""
    WITH d AS (SELECT * FROM defaults WHERE definition = 'dod2021'),
    w AS (SELECT account_id, max(missed) worst FROM performance
          GROUP BY 1)
    SELECT count(*), count(*) FILTER (WHERE trigger = 'bankruptcy'),
           count(*) FILTER (WHERE trigger = 'bankruptcy'
                             AND w.worst < 3)
    FROM d JOIN w USING (account_id)""")
print(f"2021-definition defaults: {n:,}; triggered by bankruptcy "
      f"{bk:,} ({bk / n:.1%})")
print(f"  of which never three payments behind: {never:,} "
      "(invisible to pd12)")

q, lo, low_n, med, wide = one("""
    SELECT count(*), min(cds_5y_bps),
           count(*) FILTER (WHERE cds_5y_bps < 27),
           median(cds_5y_bps) FILTER (WHERE cds_5y_bps < 27),
           max(cds_5y_bps)
    FROM market_data WHERE cds_5y_bps IS NOT NULL""")
print(f"CDS quotes: {q:,}; below 27 bp: {low_n:,} ({low_n / q:.0%}),"
      f" median {med:.1f} bp")
print(f"  lowest {lo:.1f} bp, widest {wide:,.0f} bp")
