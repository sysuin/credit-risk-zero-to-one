# timeout: 1800
# The commercial plan for 2026, measured: each step through the
# supervisor's scenario, and the whole plan's economic capital.
import fernhill
from ballast import appetite as ap
from ballast import capital
from ballast import portfolio as pf
from ballast import stress

con = fernhill.connect()
cap = ap.capital_now(con)
inp = stress.inputs(con)
P = stress.paths(con)
saved = stress.load()["summary"]["trough_sa"]
g = ap.margins(con, ap.returns(con, by="grade"))
CEILING = 500           # the highest margin Fernhill has charged, bps
# Grades 5 to 8 are repriced by their gap, up to the ceiling.
gap = {}
for label, r in g.iterrows():
    grade = int(label.split()[1])
    if 5 <= grade <= 8:
        gap[grade] = min(r.gap_bps, CEILING - r.now_bps)
print("repricing, bps: " + ", ".join(f"grade {k} +{v:.0f}"
                                     for k, v in gap.items()))
limit = ap.load_limits()["appetite"]
steps = ap.plan_steps(inp, cap["tier1"], gap, limit)
m = 1e8
print(f"\n{'supervisor scenario':<34}{'trough':>8}{'loss':>8}"
      f"{'NII':>7}{'watch':>7}")
print(f"{'today':<34}{saved['stress_2026']:>8.1%}")
rows = []
for label, d, h, p in steps:
    new = ap.reshape(inp, d, h, p)
    if label.startswith("grades"):
        plan = new                     # the 2026 plan, complete
    r = stress.project(new, P["stress_2026"], "stress_2026")
    y = r["years"]
    e = ap.company_ead(new["cb"])
    wl = e[new["cb"].groupby("company_id").grade.first() >= 9].sum()
    rows.append((label, r["trough_sa"], float(wl)))
    print(f"{label:<34}{r['trough_sa']:>8.1%}{y.loss.sum() / m:>8,.0f}"
          f"{y.nii.mean() / m:>7.0f}{wl / m:>7,.0f}")
print("loss over three years and NII a year, $m; watch = watchlist EAD")
print("the first four steps are 2026's plan; the fifth is 2027's")
whole = {}
for k in ("severe", "base"):
    whole[k] = stress.project(plan, P[k], k)["trough_sa"]
    print(f"2026 plan, {k:<8} trough {whole[k]:.1%} "
          f"(today {saved[k]:.1%})")

pools, names = pf.book(con, capital.load())
after = names.copy()
after["ead"] = after.company_id.map(ap.company_ead(plan["cb"])
                                   ).fillna(0)
model = pf.model_from(pf.load_json("correlations.json"),
                      pf.load_json("factors.json"))
res = pf.simulate(pools, after, model)
lo = pf.load()
print(f"\neconomic capital ${lo['ec_999'] / m:,.1f}m -> "
      f"${res.ec() / m:,.1f}m ({res.ec() / cap['cet1']:.1%} of CET1);")
print(f"expected loss ${lo['el'] / m:,.1f}m -> ${res.el() / m:,.1f}m; "
      f"largest client {after.ead.max() / cap['tier1']:.1%} of Tier 1")
print("saved to " + ap.save_plan({
    "steps": [{"label": a, "trough": b, "watchlist": c}
              for a, b, c in rows],
    "today": saved, "whole": whole, "gap_bps": gap,
    "ec": res.ec(), "el": res.el(),
    "largest": float(after.ead.max())}))
