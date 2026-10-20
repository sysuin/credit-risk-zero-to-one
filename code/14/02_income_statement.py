# Meridian's income statement for 2022 and 2025, each line as a
# share of the year's revenue.
import fernhill

con = fernhill.connect()
rows = {fy: r for fy, *r in con.execute("""
    SELECT fiscal_year, revenue_cents, cogs_cents, opex_cents,
           ebitda_cents, depreciation_cents, ebit_cents,
           interest_cents, tax_cents, net_income_cents
    FROM financials WHERE company_id = (
        SELECT company_id FROM companies
        WHERE name = 'Meridian Supply Co.')
      AND fiscal_year IN (2022, 2025)
    ORDER BY fiscal_year""").fetchall()}


def lines(r):
    rev, cogs, opex, ebitda, dep, ebit, interest, tax, net = r
    return [("Revenue", rev), ("Cost of goods sold", -cogs),
            ("Gross profit", rev - cogs), ("Operating expenses", -opex),
            ("EBITDA", ebitda), ("Depreciation", -dep),
            ("Operating profit", ebit), ("Interest", -interest),
            ("Tax", -tax), ("Net income", net)]


print(f"{'$000':<20}{'2022':>10}{'':>7}{'2025':>10}")
for (label, a), (_, b) in zip(lines(rows[2022]), lines(rows[2025])):
    print(f"{label:<20}{a / 1e5:>10,.0f}{a / rows[2022][0]:>7.1%}"
          f"{b / 1e5:>10,.0f}{b / rows[2025][0]:>7.1%}")
