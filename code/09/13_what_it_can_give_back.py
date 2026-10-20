# The line the accepted loans hid, put back with the bureau's help.

from _truth import applicants_with_truth
from ballast.scorecard import metrics, model, reject, sample, woe

a = applicants_with_truth()
f = reject.frames(a)
acc, unk, hold, oot = (f["accepts"], f["unknown"], f["holdout"],
                       f["oot"])
ws = woe.load_binset(sample.MARK2 / "bins.json")["worst_status_24m"]
tmpl = reject.mark2_bins() | {"worst_status_24m": ws}
nine = model.CHARACTERISTICS
ten = nine + ["worst_status_24m"]
retro = reject.training_set("bureau retro", acc, unk,
                            retro_rows=reject.retro())
everyone = a.loc[acc.index.union(unk.index)]
models = {
    "Mark II as built": (acc, acc["bad"], nine),
    "+ worst status": (acc, acc["bad"], ten),
    "retro": (retro, retro["bad"], nine),
    "retro + worst status": (retro, retro["bad"], ten),
    "truth + worst status": (everyone, everyone["truth"], ten),
}
shares = {k: d["outcome"].ne("declined").mean()
          for k, d in (("hold", hold), ("oot", oot))}
print(f"{'':<22}{'Gini':>7}{'Gini':>7}{'approve':>9}{'approve':>9}"
      f"{'coef':>6}")
print(f"{'model':<22}{'hold':>7}{'OOT':>7}{'hold':>9}{'OOT':>9}"
      f"{'ws':>6}")
for name, (fr, y, cols) in models.items():
    r = reject.fit(fr, y, cols=cols, template=tmpl)
    cells = [metrics.gini(-r.p_bad(d), d["truth"].astype(int))
             for d in (hold, oot)]
    cells += [reject.approve_best(r.p_bad(d), d["truth"], shares[k])
              for k, d in (("hold", hold), ("oot", oot))]
    c = r.coef.get("worst_status_24m")
    print(f"{name:<22}{cells[0]:>7.3f}{cells[1]:>7.3f}"
          f"{cells[2]:>9.2%}{cells[3]:>9.2%}"
          f"{'-' if c is None else f'{c:.2f}':>6}")
m1 = [metrics.gini(d["mark1_score"], d["truth"].astype(int))
      for d in (hold, oot)]
m1 += [reject.approve_best(-d["mark1_score"], d["truth"], shares[k])
       for k, d in (("hold", hold), ("oot", oot))]
print(f"{'Mark I':<22}{m1[0]:>7.3f}{m1[1]:>7.3f}{m1[2]:>9.2%}"
      f"{m1[3]:>9.2%}{'-':>6}")
print()
print(f"approve: true bad rate approving {shares['hold']:.1%} "
      f"(holdout) and {shares['oot']:.1%} (OOT)")
