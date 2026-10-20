# From EBITDA to operating cash flow: where Meridian's earnings went
# before they became cash, and what was left after capex.
import json

import fernhill
from ballast.commercial import spreading as sp
from ballast.config import ROOT

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
b = sp.cash_bridge(s)
labels = [("ebitda", "EBITDA"), ("interest", "interest"),
          ("tax", "tax"),
          ("receivables", "more receivables"),
          ("inventory", "more inventory"),
          ("payables", "more trade payables"),
          ("accruals", "more accruals"),
          ("derived", "= operating cash flow, derived"),
          ("reported", "operating cash flow, reported"),
          ("unexplained", "unexplained")]
print(f"{'$000':<34}" + "".join(f"{y:>10}" for y in b.columns))
for key, label in labels:
    print(f"{label:<34}"
          + "".join(f"{v / 1e5:>10,.0f}" for v in b.loc[key]))

r = sp.ratios(s)
fcf, div = s.loc["free_cash_flow"], s.loc["dividends"]
print(f"\n{'':<34}" + "".join(f"{y:>8}" for y in s.columns))
print(f"{'cash conversion (OCF / EBITDA)':<34}"
      + "".join(f"{v:>8.0%}" for v in r.loc["cash_conversion"]))
for label, v in [("free cash flow, $000", fcf),
                 ("dividends paid, $000", div)]:
    print(f"{label:<34}" + "".join(f"{x / 1e5:>8,.0f}" for x in v))


def m_(cents):
    return f"{'-' if cents < 0 else ''}${abs(cents) / 1e8:.1f}m"


print(f"four years: net income {m_(s.loc['net_income'].sum())}, "
      f"free cash flow {m_(fcf.sum())},")
print(f"            dividends {m_(div.sum())}")

json.dump({"years": list(s.columns),
           "ebitda": [int(v) for v in s.loc["ebitda"]],
           "ocf": [int(v) for v in s.loc["operating_cash_flow"]],
           "fcf": [int(v) for v in fcf],
           "dividends": [int(v) for v in div]},
          open(ROOT / "code/14/10_cash_bridge.json", "w"))
