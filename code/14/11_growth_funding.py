# Where the money for three years of growth came from, where the cash
# went, and what the revolver would do to Meridian's leverage if it
# were fully drawn.
import fernhill
from ballast.commercial import spreading as sp

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
a, b = s[2022], s[2025]
later = s[[2023, 2024, 2025]].sum(axis=1)
uses = [("more receivables", b.receivables - a.receivables),
        ("more inventory", b.inventory - a.inventory),
        ("more fixed assets", b.fixed_assets - a.fixed_assets)]
sources = [("profit, 2023 to 2025", later.net_income),
           ("less dividends paid", -later.dividends),
           ("more borrowings", b.total_debt - a.total_debt),
           ("more trade payables", b.payables - a.payables),
           ("less cash", a.cash - b.cash)]
for title, items in [("USES, end 2022 to end 2025", uses),
                     ("SOURCES", sources)]:
    print(f"{title:<36}{'$000':>10}{'share':>8}")
    total = sum(v for _, v in items)
    for label, v in items:
        print(f"  {label:<34}{v / 1e5:>10,.0f}{v / total:>8.0%}")
    print(f"  {'total':<34}{total / 1e5:>10,.0f}")


def m_(cents):
    return f"{'-' if cents < 0 else ''}${abs(cents) / 1e8:.1f}m"


print(f"\n2023-2025: free cash flow {m_(later.free_cash_flow)}, "
      f"dividends {m_(later.dividends)}, "
      f"new debt {m_(b.total_debt - a.total_debt)}")

limit = con.execute("SELECT amount_cents FROM credit_requests "
                    "WHERE request_id = 'R2025-117'").fetchone()[0]
rate = b.interest / b.total_debt
print(f"\nwith the ${limit / 1e8:.0f}m revolver fully drawn, "
      f"on 2025 EBITDA:")
for label, debt in [("on top of today's borrowings",
                     b.total_debt + limit),
                    ("replacing today's borrowings", limit)]:
    interest = debt * rate
    print(f"  {label:<30} debt/EBITDA {debt / b.ebitda:.2f}x, "
          f"cover {b.ebitda / interest:.2f}x")
print(f"  (interest at 2025's {rate:.1%} on every dollar)")
