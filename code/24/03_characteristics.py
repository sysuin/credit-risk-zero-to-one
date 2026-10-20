# Which of Mark I's lines moved in July 2019? A characteristic
# analysis, then the raw fields behind the lines.
import pandas as pd

from ballast import data
from ballast import monitoring as mon
from ballast.decision import policy

raw = data.load_applications(unknowns=False)
pl = raw[raw["product"].astype(str).eq("personal")]
day = pl["app_date"].astype(str)
ref = pl[(day >= "2018-07-01") & (day < "2019-07-01")]
july = pl[(day >= "2019-07-01") & (day < "2019-08-01")]
t = mon.characteristic_analysis(policy.mark1_lines(ref),
                                policy.mark1_lines(july))
print("Mark I's lines, July 2019 against Jul 2018-Jun 2019")
print(f"{'line':<24}{'PSI':>7}{'points':>9}{'points':>8}{'shift':>8}")
print(f"{'':<24}{'':>7}{'before':>9}{'July':>8}{'':>8}")
for r in t.itertuples():
    print(f"{r.line:<24}{r.psi:>7.3f}{r.reference:>9.1f}"
          f"{r.actual:>8.1f}{r.shift:>+8.1f}")
print(f"{'all lines':<24}{'':>7}{t.reference.sum():>9.1f}"
      f"{t.actual.sum():>8.1f}{t['shift'].sum():>+8.1f}")

print("\nThe raw fields, same months (PSI over the reference deciles)")
fields = {"bureau_score": ("bureau score", "{:,.1f}"),
          "age": ("age", "{:,.1f}"),
          "stated_income_cents": ("stated income", "${:,.0f}"),
          "revolving_utilisation": ("card utilisation", "{:.1%}"),
          "enquiries_6m": ("enquiries, 6 months", "{:,.2f}")}
for col, (name, f) in fields.items():
    r = pd.to_numeric(ref[col], errors="coerce").dropna()
    j = pd.to_numeric(july[col], errors="coerce").dropna()
    if col == "bureau_score":
        r, j = r[r > 0], j[j > 0]
    psi = mon.psi(r, j)
    if col == "stated_income_cents":
        r, j = r / 100, j / 100
    print(f"  {name:<22}{psi:>7.3f}   mean "
          f"{f.format(r.mean()):>8} -> {f.format(j.mean()):>8}")
