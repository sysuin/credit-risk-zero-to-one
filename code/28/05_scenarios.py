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
figures, series = {}, {}
for s in SCENARIOS:
    cf = sec.project(deal, s)          # the pool's cash, month by month
    w = sec.waterfall(cf, notes)       # who is paid it
    tt = sec.tranche_table(w)          # each class's loss and life
    unemployment, used_car = deal.paths[s][0], deal.paths[s][1]
    net = (cf.defaulted - cf.recovered).sum()
    lgd = 1 - cf.recovered.sum() / cf.defaulted.sum()
    figures[s] = [
        unemployment.mean(),
        used_car[-1],
        cf.defaulted.sum() / total * 100,
        net / total * 100,
        lgd * 100,
        w["pdl_credit"].sum() / 100,
        w["residual"].sum() / 100,
        tt.loc["A", "loss"] / 100,
        tt.loc["B", "loss"] / 100,
        tt.loc["C", "loss"] / 100,
        tt.loc["A", "wal"]]
    # Month-by-month figures for the chart, saved below.
    series[s] = {
        "net_loss": ((cf.defaulted - cf.recovered).cumsum()
                     / total).tolist(),
        "spread_used": (np.cumsum(w["pdl_credit"]) / total).tolist(),
        "released": (np.cumsum(w["residual"]) / total).tolist(),
        "notes": {n: (size - np.cumsum(w["principal"][n])).tolist()
                  for n, size, _ in notes}}

ROWS = [("unemployment, 2026-30 average %", ".2f"),
        ("used-car index, December 2030", ".1f"),
        ("defaults, % of the pool", ".2f"),
        ("net loss, % of the pool", ".2f"),
        ("loss given default %", ".1f"),
        ("defaults made good from revenue $", ",.0f"),
        ("excess spread released to C $", ",.0f"),
        ("class A lost $", ",.0f"),
        ("class B lost $", ",.0f"),
        ("class C lost $", ",.0f"),
        ("class A average life, years", ".2f")]
print(f"{'':<34}" + "".join(f"{s:>11}" for s in SCENARIOS))
for i, (label, fmt) in enumerate(ROWS):
    cells = "".join(f"{figures[s][i]:>11{fmt}}" for s in SCENARIOS)
    print(f"{label:<34}{cells}")

json.dump(series, open(ROOT / "code/28/05_scenarios.json", "w"))
