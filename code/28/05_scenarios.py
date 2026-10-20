# The deal run to the end under three of the scenarios published for
# 31 December 2025: what the pool loses and what each class is paid.
import json

import numpy as np

import fernhill
from ballast import securitisation as sec
from ballast.config import ROOT

con = fernhill.connect()
deal = sec.inputs(con)
total = float(deal.loans["balance_cents"].sum())
notes = sec.notes(deal)
SCENARIOS = ["base", "downside", "severe"]
res, series = {}, {}
for s in SCENARIOS:
    cf = sec.project(deal, s)
    w = sec.waterfall(cf, notes)
    res[s] = (cf, w, sec.tranche_table(w))
    series[s] = {
        "net_loss": ((cf.defaulted - cf.recovered).cumsum()
                     / total).tolist(),
        "spread_used": (np.cumsum(w["pdl_credit"]) / total).tolist(),
        "released": (np.cumsum(w["residual"]) / total).tolist(),
        "notes": {n: (s_ - np.cumsum(w["principal"][n])).tolist()
                  for n, s_, _ in notes}}

print(f"{'':<34}" + "".join(f"{s:>11}" for s in SCENARIOS))


def row(label, f, fmt):
    print(f"{label:<34}"
          + "".join(f"{f(s):>11{fmt}}" for s in SCENARIOS))


u = {s: deal.paths[s][0] for s in SCENARIOS}
car = {s: deal.paths[s][1] for s in SCENARIOS}
row("unemployment, 2026-30 average %", lambda s: u[s].mean(), ".2f")
row("used-car index, December 2030", lambda s: car[s][-1], ".1f")
row("defaults, % of the pool",
    lambda s: res[s][0].defaulted.sum() / total * 100, ".2f")
row("net loss, % of the pool",
    lambda s: (res[s][0].defaulted - res[s][0].recovered).sum()
    / total * 100, ".2f")
row("loss given default %",
    lambda s: (1 - res[s][0].recovered.sum()
               / res[s][0].defaulted.sum()) * 100, ".1f")
row("defaults made good from revenue $",
    lambda s: res[s][1]["pdl_credit"].sum() / 100, ",.0f")
row("excess spread released to C $",
    lambda s: res[s][1]["residual"].sum() / 100, ",.0f")
for n in ("A", "B", "C"):
    row(f"class {n} lost $", lambda s: res[s][2].loc[n, "loss"] / 100,
        ",.0f")
row("class A average life, years",
    lambda s: res[s][2].loc["A", "wal"], ".2f")

json.dump(series, open(ROOT / "code/28/05_scenarios.json", "w"))
