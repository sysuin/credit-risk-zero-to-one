# Three answers to "what is the PD of the personal loan book?"
import fernhill
from ballast import performance as perf
from ballast.config import AS_OF
from ballast.parameters import pd as pdm
from ballast.scorecard import points

con = fernhill.connect()
loans = pdm.personal_loans(con)
book = con.execute("""
    SELECT account_id, balance_cents FROM performance
    WHERE product = 'personal' AND month = ?
      AND status IN ('up_to_date', 'arrears')""", [AS_OF]).df()
book = book.merge(loans[["account_id", "score"]], on="account_id")
print(f"Personal loans open, not in default, {AS_OF:%d %b %Y}: "
      f"{len(book):,}, "
      f"${book.balance_cents.sum() / 100:,.0f}")

promise = points.bad_rate_at(book["score"]).mean()
print(f"\n1. Mark II-R's scale, from each loan's application score"
      f"\n   {promise:.2%}")

eps = perf.default_episodes(con, pdm.DEFINITION)
r = pdm.annual_default_rates(con, eps, ["personal"],
                             range(2017, 2026))
last = r[r.year == 2025].iloc[0]
print(f"\n2. Last year's default rate (dod2021, Chapter 6's measure)"
      f"\n   {last.rate:.2%}  ({last.defaults:,} of "
      f"{last.at_risk:,} loans open on 1 January 2025)")

print("\n3. The long-run average of the yearly rates, 2017-2025"
      f"\n   {r.rate.mean():.2%}  (lowest {r.rate.min():.2%} in "
      f"{r.year[r.rate.idxmin()]}, highest {r.rate.max():.2%} in "
      f"{r.year[r.rate.idxmax()]})")
