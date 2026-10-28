# The cycle in Fernhill's own book: each product's default rate, year
# by year, beside the average unemployment rate.
import pandas as pd

import fernhill
from ballast import performance as perf
from ballast.parameters import pd as pdm

con = fernhill.connect()
products = ["personal", "card", "auto", "mortgage", "sme_term",
            "sme_overdraft", "sme_emergency"]
short = ["pers", "card", "auto", "mortg", "term", "o/d", "emerg"]
eps = perf.default_episodes(con, pdm.DEFINITION)
r = pdm.annual_default_rates(con, eps, products, range(2017, 2026))
t = r.pivot(index="year", columns="product", values="rate")[products]
u = pdm.unemployment(con)
u_year = u.groupby(u.index.year).mean()
print("Default rate (dod2021), accounts open on 1 January; "
      "unemployment %")
head = "".join(f"{s:>7}" for s in short)
print(f"{'year':<6}{head}{'unemp':>7}")
for y, row in t.iterrows():
    cells = ""
    for v in row:
        # a product with no accounts open that year shows a dash
        if pd.isna(v):
            cells += f"{'-':>7}"
        else:
            cells += f"{v:>7.2%}"
    print(f"{y:<6}{cells}{u_year[y]:>7.2f}")
print(f"{'mean':<6}" + "".join(f"{v:>7.2%}" for v in t.mean())
      + f"{u_year.loc[2017:2025].mean():>7.2f}")
ratio = t.max() / t.min()
print(f"{'max/min':<6}" + "".join(f"{v:>7.1f}" for v in ratio))
