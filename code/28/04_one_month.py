# One month of the deal in the base scenario, April 2026, the first
# month with recoveries: what the pool collects and who is paid it.
import json

import fernhill
from ballast import securitisation as sec
from ballast.config import ROOT

con = fernhill.connect()
deal = sec.inputs(con)
cf = sec.project(deal, "base")
notes = sec.notes(deal)
w = sec.waterfall(cf, notes)
M = 4                                    # April 2026
m, row = M - 1, cf.loc[M]
cpn = sec.coupons(deal)


def line(label, cents, indent=2):
    print(f"{' ' * indent}{label:<40}{cents / 100:>14,.0f}")


print(f"month {M} of the deal: April 2026, base scenario    dollars")
line("pool at the start of the month", row.balance, 0)
print("collected")
for k, label in [("interest", "interest"),
                 ("recovered", "recoveries (cars sold)"),
                 ("scheduled", "scheduled principal"),
                 ("prepaid", "prepayments")]:
    line(label, row[k])
line("defaulted this month (owed, not paid)", row.defaulted, 0)
print("revenue: interest and recoveries, in order")
steps = [(f"1 servicing fee ({sec.SERVICING_PCT:.2f}% a year)",
          w["fee"][m]),
         (f"2 class A interest ({cpn['A']:.2f}%)",
          w["interest"]["A"][m]),
         (f"3 class B interest ({cpn['B']:.2f}%)",
          w["interest"]["B"][m]),
         ("4 defaults made good (to the PDL)", w["pdl_credit"][m]),
         ("5 released to class C", w["residual"][m])]
for label, v in steps:
    line(label, v)
print("principal: scheduled, prepaid and step 4, in order")
for n in ("A", "B", "C"):
    line(f"class {n}", w["principal"][n][m])
end = {n: s - w["principal"][n][:M].sum() for n, s, _ in notes}
print("after the month: " + ", ".join(
    f"{n} ${v / 1e8:,.2f}m" for n, v in end.items()))

json.dump({"month": M, "flows": {k: float(row[k]) for k in sec.FLOWS},
           "steps": [[a, float(b)] for a, b in steps],
           "principal": {n: float(w["principal"][n][m])
                         for n in ("A", "B", "C")}},
          open(ROOT / "code/28/04_one_month.json", "w"), indent=1)
