# Ballast's LGD and EAD parameters by product, as Chapters 20 to 22
# will use them, saved to data/ballast/parameters/.
import fernhill
from ballast.parameters import ead, lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
rates = lgd.discount_rates(con, w)
done = lgd.realised(w, f, rates)
done = done[done["default_month"] <= "2021-12-31"]
old = lgd.pooled(done)["lgd"]

est = {}
print(f"{'product':<15}{'workouts':>9}{'2016-21':>9}{'LGD':>7}"
      f"{'downturn':>10}{'worst':>7}{'cured':>7}")
for p, g in w.groupby("product"):
    e = lgd.estimate(g, f, rates)
    est[p] = e
    print(f"{p:<15}{e['workouts']:>9,}{old[p]:>9.1%}{e['lgd']:>7.1%}"
          f"{e['downturn']:>10.1%}{e['worst_year'] or '-':>7}"
          f"{e['cure_rate']:>7.0%}")
print("2016-21: finished workouts only; LGD: every year, unfinished")
print("ones completed by the recovery curve; worst: the year that")
print("sets the downturn LGD (30 workouts or more, to 2023)")
lgd.save({"definition": w.attrs["definition"],
          "discount": f"cost of funds + {lgd.DISCOUNT_PREMIUM_PCT}",
          "products": est})

s = ead.ccf_sample(con, "card")
card = ead.fit_ccf(s[s["missed0"] == 0])
od = ead.ccf_sample(con, "sme_overdraft")
ccf = {"card": {b: float(r["ccf"]) for b, r in card.iterrows()},
       "sme_overdraft": ead.pooled_ccf(od[od["missed0"] == 0]),
       "revolver": ead.pooled_ccf(ead.revolver_sample(con))}
ead.save({"horizon_months": ead.HORIZON, "bands": ead.BANDS[:-1],
          "ccf": ccf})
print("\nCCF, cards, by use of the limit a year before:")
print("  " + "  ".join(f"{b} {v:.2f}" for b, v in ccf["card"].items()))
print(f"CCF, sme_overdraft {ccf['sme_overdraft']:.2f}; "
      f"commercial revolvers {ccf['revolver']:.2f}")
print(f"saved: {lgd.PARAMS.name}, {ead.PARAMS.name} in "
      f"data/ballast/{lgd.PARAMS.parent.name}/")
