# Profit against cash, year by year: what Meridian earned, what its
# operations brought in, what it spent on equipment, what it paid
# its owners, and its bank balance at each year end.
import fernhill

con = fernhill.connect()
rows = con.execute("""
    SELECT fiscal_year, net_income_cents, ebitda_cents,
           operating_cash_flow_cents, capex_cents, dividends_cents,
           cash_cents
    FROM financials JOIN companies USING (company_id)
    WHERE name = 'Meridian Supply Co.'
    ORDER BY fiscal_year""").fetchall()
print(f"{'$000':<6}{'net':>9}{'EBITDA':>9}{'operating':>11}"
      f"{'capex':>8}{'dividends':>11}{'cash at':>10}")
print(f"{'':<6}{'income':>9}{'':>9}{'cash flow':>11}{'':>8}{'':>11}"
      f"{'year end':>10}")
widths = (9, 9, 11, 8, 11)
totals = [0] * 5
for row in rows:
    year, values, cash = row[0], row[1:6], row[6]
    cells = [f"{v / 1e5:>{w},.0f}" for v, w in zip(values, widths)]
    print(f"{year:<6}" + "".join(cells) + f"{cash / 1e5:>10,.0f}")
    # Add this year's five flows to the running totals.
    totals = [t + v for t, v in zip(totals, values)]
cells = [f"{t / 1e5:>{w},.0f}" for t, w in zip(totals, widths)]
print(f"{'total':<6}" + "".join(cells))
