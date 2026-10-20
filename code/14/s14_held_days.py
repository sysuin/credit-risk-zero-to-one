# Exercise 14.2: Meridian with receivable days held at 2022's 48 days,
# everything else in the cash bridge as reported.
import fernhill
from ballast.commercial import spreading as sp

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
r = sp.ratios(s)
held = s.loc["revenue"] * r.loc["receivable_days", 2022] / sp.DAYS
actual = s.loc["receivables"]
d_actual = actual.diff()
d_held = held.diff()
ocf = s.loc["operating_cash_flow"] + (d_actual - d_held)
years = list(s.columns[1:])
print(f"{'$000':<30}" + "".join(f"{y:>10}" for y in years))
rows = [("receivables, held at 48 days", held),
        ("receivables, as reported", actual),
        ("operating cash flow, held", ocf),
        ("operating cash flow, reported", s.loc["operating_cash_flow"])]
for label, v in rows:
    print(f"{label:<30}" + "".join(f"{v[y] / 1e5:>10,.0f}"
                                   for y in years))
print(f"{'cash conversion, held':<30}" + "".join(
    f"{(ocf / s.loc['ebitda'])[y]:>10.0%}" for y in years))
print(f"{'cash conversion, reported':<30}" + "".join(
    f"{r.loc['cash_conversion', y]:>10.0%}" for y in years))
extra = (ocf - s.loc["operating_cash_flow"])[years].sum()
print(f"extra cash over 2023-2025: ${extra / 1e8:.1f}m")
