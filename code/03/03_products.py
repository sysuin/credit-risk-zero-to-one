# What Fernhill lent, for how long, at what rate, against what.
import fernhill

con = fernhill.connect()

rows = con.execute("""
    SELECT product, count(*),
           quantile_disc(amount_cents, [0.1, 0.5, 0.9]),
           min(term_months), median(term_months), max(term_months),
           quantile_disc(rate_pct, [0.1, 0.5, 0.9]),
           -- loan-to-value at opening, where there is collateral
           median(amount_cents / collateral_value_cents),
           quantile_cont(amount_cents / collateral_value_cents, 0.9)
    FROM accounts
    GROUP BY product
    ORDER BY median(amount_cents) DESC
""").fetchall()

d = lambda c: f"${c / 100:,.0f}"  # noqa: E731
print("Amount lent (the limit, for a card or overdraft), and term")
print(f"{'product':<14}{'p10':>9}{'median':>10}{'p90':>11}"
      "   term, months")
for p, n, amt, t0, tm, t1, *_ in rows:
    if tm is None:
        term = "none"
    elif t0 == t1:
        term = f"{tm:.0f}"
    else:
        term = f"{t0:.0f}-{t1:.0f}, median {tm:.0f}"
    print(f"{p:<14}{d(amt[0]):>9}{d(amt[1]):>10}{d(amt[2]):>11}"
          f"   {term}")

print()
print("Interest rate at opening (% a year), and loan-to-value")
print(f"{'product':<14}{'p10':>7}{'median':>8}{'p90':>7}"
      f"{'LTV median':>12}{'LTV p90':>9}")
for p, *_, rate, ltv, ltv90 in rows:
    lv = f"{ltv:>12.0%}{ltv90:>9.0%}" if ltv else f"{'-':>12}{'-':>9}"
    print(f"{p:<14}{rate[0]:>7.2f}{rate[1]:>8.2f}{rate[2]:>7.2f}{lv}")
