# Exercise 14.1: Meridian's working-capital days on the average of the
# opening and closing balances, beside the year-end version.
import fernhill
from ballast.commercial import spreading as sp

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
avg = (s + s.shift(1, axis=1)) / 2
end = sp.ratios(s)
years = list(s.columns[1:])
print(f"{'':<22}" + "".join(f"{y:>9}" for y in years))
for basis, frame in [("end", s), ("avg", avg)]:
    rec = sp.DAYS * frame.loc["receivables"] / s.loc["revenue"]
    inv = sp.DAYS * frame.loc["inventory"] / s.loc["cogs"]
    pay = sp.DAYS * frame.loc["payables"] / s.loc["cogs"]
    for label, v in [("receivable days", rec), ("inventory days", inv),
                     ("payable days", pay),
                     ("cash cycle", rec + inv - pay)]:
        print(f"{basis + ' ' + label:<22}"
              + "".join(f"{v[y]:>9.1f}" for y in years))
check = end.loc["cash_cycle", years]
print("year-end cycle as in the chapter: "
      + ", ".join(f"{v:.1f}" for v in check))
