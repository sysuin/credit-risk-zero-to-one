# Ballast's PD, fitted and saved for Chapter 20: the calibration, the
# 12-month model, a hazard model for every product, and term
# structures under every scenario of the 31 December 2025 date.
import numpy as np
import pandas as pd

import fernhill
from ballast.commercial import migration as mg
from ballast.commercial import rating as rt
from ballast.config import AS_OF
from ballast.parameters import pd as pdm

con = fernhill.connect()
loans = pdm.personal_loans(con)
d = loans.open_month.dt.date
fit = loans[(d >= pdm.CALIBRATE_FROM) & (d <= pdm.CALIBRATE_TO)]
cal = pdm.fit_calibration(fit.score, fit.d12)
panel = pdm.account_months(con, loans)
model = pdm.fit_pd_model(panel[panel.complete])
lr = pdm.long_run_unemployment(con)
saved = [pdm.save_json("pd_calibration.json", cal.to_dict()),
         pdm.save_json("pd_model.json", model.to_dict()
                       | {"long_run_unemployment": lr})]

LIFE = {"personal": 60, "card": 120, "auto": 72, "mortgage": 360,
        "sme_term": 84, "sme_overdraft": 120, "sme_emergency": 72}
paths = {"long_run": None}
for s in ["base", "upside", "downside", "severe", "stress_2026"]:
    u = pdm.unemployment(con, s)
    paths[s] = u[u.index > pd.Timestamp(AS_OF)].to_numpy()
models, curves, rows = {}, [], []
print(f"{'product':<14}{'accounts':>9}{'defaults':>9}{'u coef':>8}"
      f"{'life':>6}{'base':>7}{'severe':>8}")
for product, life in LIFE.items():
    dur = pdm.durations(con, product)
    hm = pdm.fit_hazard(product, pdm.person_months(
        dur, pdm.unemployment(con)))
    models[product] = hm.to_dict()
    mix = dur.band.value_counts(normalize=True)
    pd_life = {}
    for s, path in paths.items():
        u = (np.full(life, lr) if path is None else
             np.r_[path, np.full(max(life - len(path), 0), path[-1])])
        lifetime = {}
        for b in hm.bands:
            ts = hm.term_structure(b, u[:life])
            curves.append(ts.assign(product=product, band=b,
                                    scenario=s))
            lifetime[b] = ts.cumulative_pd.iloc[-1]
            rows.append({"product": product, "band": b, "scenario": s,
                         "pd_12m": ts.cumulative_pd[11],
                         "pd_lifetime": lifetime[b]})
        pd_life[s] = sum(mix[b] * lifetime[b] for b in hm.bands)
    print(f"{product:<14}{len(dur):>9,}{(dur.event == 1).sum():>9,}"
          f"{hm.default['u']:>8.3f}{life:>6}{pd_life['base']:>7.1%}"
          f"{pd_life['severe']:>8.1%}")

saved.append(pdm.save_json("pd_hazard.json", {
    "definition": pdm.DEFINITION, "hazard_edges": pdm.HAZARD_EDGES,
    "score_edges": pdm.SCORE_EDGES, "clock": pdm.CLOCK,
    "long_run_unemployment": lr, "models": models}))
cols = ["product", "band", "scenario", "month", "hazard", "exit",
        "survival", "marginal_pd", "cumulative_pd"]
ts = pd.concat(curves)[cols]
pdm.PARAMS.mkdir(parents=True, exist_ok=True)
ts.to_parquet(pdm.PARAMS / "pd_term_structures.parquet", index=False)
pd.DataFrame(rows).to_csv(pdm.PARAMS / "pd_scenarios.csv",
                          index=False, float_format="%.6f")
saved += ["data/ballast/parameters/pd_term_structures.parquet",
          "data/ballast/parameters/pd_scenarios.csv"]

rv = rt.reviews(con)
dev = rv[rv.window_complete]
g = dev.groupby("grade").default_12m.agg(["size", "sum"])
post = pdm.bayes_scale(g["size"], g["sum"], g.index)
life = mg.project(mg.matrix(mg.panel(rv, "grade")), 5)
saved.append(pdm.save_json("pd_commercial.json", {
    "master_scale": rt.MASTER_SCALE,
    "bayes_mean": post["mean"].to_dict(),
    "pluto_tasche_90": dict(zip(g.index.tolist(), pdm.pluto_tasche(
        g["size"], g["sum"], 0.9).tolist())),
    "matrix_cumulative": {k: v.tolist() for k, v in life.iterrows()}}))

print(f"\n{len(ts):,} term-structure rows; saved:")
for path in saved:
    print(f"  {path:<52}{(pdm.ROOT / path).stat().st_size:>8,} B")
back = pdm.load_hazards()["personal"]
same = np.allclose(back.hazard([12], "580-599", [5.0]),
                   pdm.HazardModel(**models["personal"]).hazard(
                       [12], "580-599", [5.0]))
print(f"Reloaded: calibration {pdm.load_calibration().method}, "
      f"hazards for {len(pdm.load_hazards())} products, same: {same}")
