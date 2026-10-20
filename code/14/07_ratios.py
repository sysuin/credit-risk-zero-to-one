# Meridian's profitability, leverage, cover and liquidity, four years.
import json

import fernhill
from ballast.commercial import spreading as sp
from ballast.config import ROOT

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
r = sp.ratios(s)
show = [
    ("revenue_growth", "revenue growth", "%"),
    ("gross_margin", "gross margin", "%"),
    ("ebitda_margin", "EBITDA margin", "%"),
    ("net_margin", "net margin", "%"),
    ("leverage", "debt / EBITDA", "x"),
    ("net_leverage", "(debt - cash) / EBITDA", "x"),
    ("interest_cover", "EBITDA / interest", "x"),
    ("ebit_cover", "EBIT / interest", "x"),
    ("current_ratio", "current ratio", "x"),
    ("quick_ratio", "quick ratio", "x"),
    ("equity_ratio", "equity / total assets", "%"),
    ("payout", "dividends / net income", "%"),
]
print(f"{'':<26}" + "".join(f"{y:>10}" for y in r.columns))
for key, label, unit in show:
    cells = ["" if v != v else f"{v:.1%}" if unit == "%" else
             f"{v:.2f}x" for v in r.loc[key]]
    print(f"{label:<26}" + "".join(f"{c:>10}" for c in cells))

lines = ["revenue", "ebitda", "net_income", "receivables",
         "inventory", "cash", "total_debt", "operating_cash_flow",
         "dividends"]
json.dump({"years": list(s.columns),
           "lines": {k: [int(v) for v in s.loc[k]] for k in lines}},
          open(ROOT / "code/14/07_ratios.json", "w"))
