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


def dollars(cents):
    """Cents as whole dollars, such as $10,000."""
    return f"${cents / 100:,.0f}"


print("Amount lent (the limit, for a card or overdraft), and term")
print(f"{'product':<14}{'p10':>9}{'median':>10}{'p90':>11}"
      "   term, months")
for (product, _, amount, shortest, typical, longest,
     rate, ltv, ltv_p90) in rows:
    if typical is None:
        term = "none"
    elif shortest == longest:
        term = f"{typical:.0f}"
    else:
        term = f"{shortest:.0f}-{longest:.0f}, median {typical:.0f}"
    print(f"{product:<14}{dollars(amount[0]):>9}"
          f"{dollars(amount[1]):>10}{dollars(amount[2]):>11}"
          f"   {term}")

print()
print("Interest rate at opening (% a year), and loan-to-value")
print(f"{'product':<14}{'p10':>7}{'median':>8}{'p90':>7}"
      f"{'LTV median':>12}{'LTV p90':>9}")
for (product, _, amount, shortest, typical, longest,
     rate, ltv, ltv_p90) in rows:
    # Products with no collateral have no loan-to-value.
    if ltv:
        ltv_cells = f"{ltv:>12.0%}{ltv_p90:>9.0%}"
    else:
        ltv_cells = f"{'-':>12}{'-':>9}"
    print(f"{product:<14}{rate[0]:>7.2f}{rate[1]:>8.2f}"
          f"{rate[2]:>7.2f}{ltv_cells}")
