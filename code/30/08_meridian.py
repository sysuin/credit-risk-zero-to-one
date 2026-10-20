# Meridian through the lens of the supply-chain-finance failures: its
# working capital, what paid its dividends, and what a lender lending
# against its receivables or blind to bank-financed payables would see.
import json

import fernhill
from ballast.commercial import spreading as sp
from ballast.commercial import structure as st
from ballast.config import ROOT

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
r = sp.ratios(s)
rf = sp.roll_forward(s)
print(f"{'Meridian':<26}" + "".join(f"{y:>9}" for y in s.columns))
for name, row, fmt in (
        ("receivable days", r.loc["receivable_days"], "{:>9.0f}"),
        ("trade payable days", r.loc["payable_days"], "{:>9.0f}"),
        ("cash conversion", r.loc["cash_conversion"], "{:>9.0%}")):
    print(f"{name:<26}" + "".join(fmt.format(v) for v in row))
for name, row in (("free cash flow $m", s.loc["free_cash_flow"]),
                  ("dividends paid $m", s.loc["dividends"]),
                  ("new borrowing $m", rf.loc["new_borrowing"])):
    print(f"{name:<26}" + "".join(
        f"{v / 1e8:>9.2f}" if y in row.index else f"{'':>9}"
        for y, v in zip(s.columns, row.reindex(s.columns))))
allowed = [st.permitted_distribution(int(s.loc["net_income", y - 1]),
                                     float(r.loc["leverage", y - 1]))
           for y in s.columns[1:]]
print(f"{'rule allows $m':<26}{'':>9}"
      + "".join(f"{a / 1e8:>9.2f}" for a in allowed))
c = s[2025]
print("\nIf Meridian's trade payables were bank-financed, 2025")
print(f"  {'share financed':<24}{'debt $m':>9}{'debt/EBITDA':>13}")
for share in (0.0, 0.25, 0.5):
    debt = c.total_debt + share * c.payables
    print(f"  {share:<24.0%}{debt / 1e8:>9.1f}"
          f"{debt / c.ebitda:>12.2f}x")
print("\nBorrowing base on 2025's receivables and stock")
print(f"  {'receivables ineligible':<24}{'base $m':>9}")
for bad in (0.15, 0.25, 0.40):
    bb = st.borrowing_base(c.receivables, c.inventory,
                           round(c.receivables * bad))
    print(f"  {bad:<24.0%}{bb.base / 1e8:>9.2f}")
(ROOT / "code" / "30" / "08_meridian.json").write_text(json.dumps({
    "year": [int(y) for y in s.columns[1:]],
    "fcf": [round(s.loc["free_cash_flow", y] / 1e8, 3)
            for y in s.columns[1:]],
    "dividends": [round(s.loc["dividends", y] / 1e8, 3)
                  for y in s.columns[1:]],
    "borrowing": [round(rf.loc["new_borrowing", y] / 1e8, 3)
                  for y in s.columns[1:]],
    "receivable_days": [round(float(r.loc["receivable_days", y]), 1)
                        for y in s.columns]}) + "\n")
