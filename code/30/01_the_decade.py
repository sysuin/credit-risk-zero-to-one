# Fernhill's decade in one table: the economy, rates, and how often
# its consumer and commercial borrowers defaulted, year by year.
import json

import fernhill
from ballast import performance as perf
from ballast.config import ROOT
from ballast.parameters import pd as pdm

con = fernhill.connect()
macro = con.execute("""
    SELECT year(month) AS year, avg(unemployment_pct) AS unemp,
           arg_max(policy_rate_pct, month) AS policy,
           arg_max(house_price_index, month) AS house
    FROM macro GROUP BY 1 ORDER BY 1""").df().set_index("year")
eps = perf.default_episodes(con, "dod2021")
years = range(2017, 2026)
consumer = ["personal", "card", "auto", "mortgage"]
rates = pdm.annual_default_rates(con, eps, consumer, years)
both = rates.groupby("year")[["at_risk", "defaults"]].sum()
corp = con.execute("""
    SELECT year(default_month) AS year, count(*) AS n
    FROM corporate_defaults GROUP BY 1 ORDER BY 1""").df()
corp = corp.set_index("year")["n"]

print(f"{'':<6}{'unemp-':>8}{'policy':>8}{'house':>8}"
      f"{'consumer':>10}{'business':>10}")
print(f"{'year':<6}{'loyment':>8}{'rate':>8}{'prices':>8}"
      f"{'default':>10}{'defaults':>10}")
for y in years:
    m = macro.loc[y]
    chg = m.house / macro.loc[y - 1, "house"] - 1
    r = both.loc[y, "defaults"] / both.loc[y, "at_risk"]
    print(f"{y:<6}{m.unemp:>7.2f}%{m.policy:>7.2f}%{chg:>+8.1%}"
          f"{r:>10.2%}{int(corp.get(y, 0)):>10}")
print("unemployment: the year's average; policy rate: December;")
print("house prices: change in the index over the year; consumer")
print("default: new defaults (2021 definition) among personal, card,")
print("car and mortgage accounts open and performing on 1 January;")
print("business defaults: commercial clients")

monthly = con.execute("""
    SELECT strftime(month, '%Y-%m') AS m, unemployment_pct AS u,
           policy_rate_pct AS r FROM macro ORDER BY month""").df()
(ROOT / "code" / "30" / "01_the_decade.json").write_text(json.dumps({
    "month": list(monthly.m), "unemployment": list(monthly.u),
    "policy": list(monthly.r),
    "default_year": list(years),
    "default_rate": [round(both.loc[y, "defaults"]
                           / both.loc[y, "at_risk"], 5) for y in years],
}) + "\n")
