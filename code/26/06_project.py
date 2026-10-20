# Three years of the base, severe and supervisory scenarios on
# Fernhill's static book: defaults and losses by product, and the
# engine's default rates beside the satellite models'.
# timeout: 900
import json

import fernhill
from ballast import stress

con = fernhill.connect()
inp = stress.inputs(con)
paths = stress.paths(con, stress.SCENARIOS)
res = {k: stress.project(inp, p, k) for k, p in paths.items()}
stress.save(res, paths, {"year_zero": stress.year_zero(inp)})

pr = {k: r["products"].set_index(["product", "year"])
      for k, r in res.items()}
names = {"personal": "personal", "card": "card", "auto": "car",
         "mortgage": "mortgage", "sme_term": "SME term",
         "sme_overdraft": "overdraft", "sme_emergency": "emergency",
         "commercial_term": "comm. term",
         "commercial_revolver": "revolver"}
print("Default rate in 2027 (share of accounts) and loss over")
print("2026-2028, $m, on the book of 31 Dec 2025 held constant")
print(f"{'':<12}{'base':>7}{'severe':>7}{'stress':>7}"
      f"{'base':>9}{'severe':>8}{'stress':>8}")
for p, n in names.items():
    rates = [pr[k].loc[(p, 2027), "rate"] for k in stress.SCENARIOS]
    loss = [pr[k].loc[p, "loss"].sum() / 1e8 for k in stress.SCENARIOS]
    print(f"{n:<12}" + "".join(f"{v:>7.2%}" for v in rates)
          + f"{loss[0]:>9.1f}{loss[1]:>8.1f}{loss[2]:>8.1f}")
groups = (("retail", False), ("commercial", True), ("all", None))
for lab, sel in groups:
    tot = []
    for r in res.values():
        g = r["products"]
        if sel is not None:
            g = g[g["product"].str.startswith("commercial") == sel]
        tot.append(g.loss.sum() / 1e8)
    print(f"{lab:<33}{tot[0]:>9.1f}{tot[1]:>8.1f}{tot[2]:>8.1f}")

print("\nstress_2026 by year")
print(f"{'':<6}{'unemp':>7}{'rate':>7}{'defaults':>10}"
      f"{'exposure $m':>13}{'loss $m':>9}{'LGD':>7}")
for r in res["stress_2026"]["years"].itertuples():
    print(f"{r.year:<6}{r.u:>7.2f}{r.policy:>7.2f}{r.defaults:>10,.0f}"
          f"{r.default_ead / 1e8:>13,.1f}{r.loss / 1e8:>9.1f}"
          f"{r.loss / r.default_ead:>7.1%}")

print("\n2027 default rates, base and stress: the engine (today's")
print("book) against the satellite models (the decade's average book)")
print(f"{'':<12}{'engine':>8}{'stress':>8}{'x':>6}{'satellite':>11}"
      f"{'stress':>8}{'x':>6}")
h = stress.default_history(con)
yb = stress.annual(paths["base"]).loc[2027]
ys = stress.annual(paths["stress_2026"]).loc[2027]
rows = [(p, ("u",)) for p in ("personal", "card", "auto", "mortgage",
                              "sme_term", "sme_overdraft")]
for p, drv in rows + [("commercial", ("u", "policy"))]:
    f = stress.fit_satellite(h, p, drv)
    sb = stress.satellite_rate(f, {"u": yb.u, "policy": yb.policy})[0]
    ss = stress.satellite_rate(f, {"u": ys.u, "policy": ys.policy})[0]
    if p == "commercial":
        e = [res[k]["products"].query("year == 2027 and "
             "product.str.startswith('commercial')").defaults.sum()
             / len(inp["cb"]) for k in ("base", "stress_2026")]
    else:
        e = [pr[k].loc[(p, 2027), "rate"] for k in ("base",
                                                     "stress_2026")]
    n = names.get(p, p)
    print(f"{n:<12}{e[0]:>8.2%}{e[1]:>8.2%}{e[1] / e[0]:>6.1f}"
          f"{sb:>11.2%}{ss:>8.2%}{ss / sb:>6.1f}")

eng = {p: pr["stress_2026"].loc[(p, 2027), "rate"] for p, _ in rows}
eng["commercial"] = e[1]
with open("code/26/06_project.json", "w") as f:
    json.dump({"engine_2027": eng}, f)
