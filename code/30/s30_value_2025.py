# Exercise 30.3: the fixed-rate loans of listing 07 valued at December
# 2021's, 2023's and 2025's funding curves.
import fernhill
from ballast import loanmath, pricing
from ballast import securitisation as sec

con = fernhill.connect()
mkt = {str(r["month"])[:4]: r for r in con.execute(
    "SELECT * FROM market_rates WHERE month IN (DATE '2021-12-31', "
    "DATE '2023-12-31', DATE '2025-12-31') ORDER BY month"
).df().to_dict("records")}
book = con.execute("""
    SELECT a.product, p.balance_cents AS bal, p.rate_pct AS rate,
           a.payment_cents AS pay
    FROM performance p JOIN accounts a USING (account_id)
    WHERE p.month = DATE '2021-12-31' AND a.rate_type = 'fixed'
      AND a.product IN ('personal', 'auto', 'mortgage')
      AND p.missed = 0 AND p.balance_cents > 0
      AND NOT p.payment_holiday ORDER BY a.account_id""").df()
book["n"] = sec.remaining_payments(book.bal, book.rate, book.pay)
for year in ("2021", "2023", "2025"):
    book[year] = [loanmath.present_value(
        [r.pay] * int(r.n), r.rate + pricing.ftp_pct(mkt[year], r.n)
        - pricing.ftp_pct(mkt["2021"], r.n)) for r in book.itertuples()]
print(f"{'':<10}{'Dec 2021 $m':>12}{'at 2023':>10}{'at 2025':>10}")
for prod, g in list(book.groupby("product")) + [("all", book)]:
    base = g["2021"].sum()
    print(f"{prod:<10}{base / 1e8:>12.1f}"
          f"{g['2023'].sum() / base - 1:>10.1%}"
          f"{g['2025'].sum() / base - 1:>10.1%}")
for y in ("2021", "2023", "2025"):
    print(f"funding curve at two years, Dec {y}: "
          f"{pricing.ftp_pct(mkt[y], 24):.2f}%")
