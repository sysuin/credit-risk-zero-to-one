# Chapter 1's charge-offs taken apart by the policy each loan was
# booked under, reconciled to Chapter 1's dollars, with the balance
# that was at risk of being charged off.
import json

import fernhill
from _chargeoffs import COHORTS, account_months
from ballast.config import ROOT

con = fernhill.connect()
m = account_months(con)
m["year"] = m["month"].dt.year
m = m[m["year"].between(2021, 2025)]
years = list(range(2021, 2025 + 1))
off = m.pivot_table(index="cohort", columns="year", values="off_cents",
                    aggfunc="sum", fill_value=0)
risk = m.pivot_table(index="cohort", columns="year",
                     values="risk_cents", aggfunc="sum", fill_value=0)
ch1 = {r["year"]: r["lost"]
       for r in json.loads((ROOT / "code/01/02_charge_offs.json")
                           .read_text())}

print(f"{'charged off, $':<18}" + "".join(f"{y:>10}" for y in years))
for name, _ in COHORTS:
    print(f"{name:<18}" + "".join(f"{off.loc[name, y] / 100:>10,.0f}"
                                  for y in years))
print(f"{'all':<18}" + "".join(f"{off[y].sum() / 100:>10,.0f}"
                               for y in years))
print(f"{'Chapter 1':<18}" + "".join(f"{ch1[y] / 100:>10,.0f}"
                                     for y in years))
same = all(int(off[y].sum()) == ch1[y] for y in years)
print(f"equal to the cent: {'yes' if same else 'NO'}")

print(f"\n{'at risk, $m':<18}" + "".join(f"{y:>10}" for y in years))
for name, _ in COHORTS:
    print(f"{name:<18}" + "".join(f"{risk.loc[name, y] / 1.2e9:>10.1f}"
                                  for y in years))
print(f"{'all':<18}" + "".join(f"{risk[y].sum() / 1.2e9:>10.1f}"
                               for y in years))
print("at risk: average month-end balance of loans six months old or")
print("more and not yet charged off")

(ROOT / "code/31/03_charge_offs.json").write_text(json.dumps(
    {"years": years,
     "off": {name: [int(off.loc[name, y]) for y in years]
             for name, _ in COHORTS}}) + "\n")
