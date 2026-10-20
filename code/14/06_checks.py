# Before any ratio: does the arithmetic hold, and does each year roll
# forward into the next?
import fernhill
from ballast.commercial import spreading as sp

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
found = sp.problems(s)
print(f"arithmetic problems in {len(s.columns)} years: {len(found)}")
for p in found:
    print("  " + p)

roll = sp.roll_forward(s)
labels = [
    ("equity_change", "change in equity"),
    ("net_income", "  net income"),
    ("dividends", "  dividends paid"),
    ("equity_other", "  not explained"),
    ("fixed_change", "change in fixed assets"),
    ("capex_less_dep", "  capex less depreciation"),
    ("fixed_other", "  not explained"),
    ("cash_change", "change in cash"),
    ("free_cash_flow", "  free cash flow"),
    ("new_borrowing", "  new borrowing"),
    ("dividends", "  dividends paid"),
    ("cash_other", "  not explained"),
]
print(f"\n{'$000':<32}" + "".join(f"{y:>10}" for y in roll.columns))
for key, label in labels:
    print(f"{label:<32}" + "".join(
        f"{v / 1e5:>10,.0f}" for v in roll.loc[key]))

rate = s.loc["interest"] / s.loc["total_debt"]
print(f"\n{'':<22}" + "".join(f"{y:>10}" for y in rate.index))
print(f"{'interest / borrowings':<22}"
      + "".join(f"{r:>10.1%}" for r in rate))
