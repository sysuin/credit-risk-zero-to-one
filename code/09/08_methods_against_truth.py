# Every method scored against the truth, on applicants it never saw.
# timeout: 300
import json

import numpy as np

from _truth import applicants_with_truth
from ballast.config import ROOT, SEED
from ballast.scorecard import metrics, reject

a = applicants_with_truth()
f = reject.frames(a)
acc, unk, hold, oot = (f["accepts"], f["unknown"], f["holdout"],
                       f["oot"])
fits = reject.fit_all(acc, unk, reject.retro(),
                      np.random.default_rng(SEED))
fits["reweight, cap 10"] = reject.fit(
    *(lambda t: (t, t["bad"], t["weight"]))(reject.training_set(
        "reweight", acc, unk, cap=10)))
train = acc.index.union(unk.index)
everyone = a.loc[train]
fits["truth (ceiling)"] = reject.fit(everyone, everyone["truth"])
order = ["ignore", "reweight", "reweight, cap 10", "hard cut-off",
         "parcelling", "fuzzy", "bureau retro", "truth (ceiling)"]

share = hold["outcome"].ne("declined").mean()
fern = hold.loc[hold["outcome"].ne("declined"), "truth"].mean()
print(f"holdout: {len(hold):,} applicants, {int(hold['truth'].sum())} "
      f"true bads; out of time: {len(oot):,}")
print(f"Fernhill approved {share:.1%}; true bad rate among them "
      f"{fern:.2%}")
print()
print(f"{'':<17}{'Gini':>6}{'Gini':>6}{'declines':>12}{'booked':>12}"
      f"{'approve':>9}")
print(f"{'method':<17}{'hold':>6}{'OOT':>6}{'pred':>6}{'true':>6}"
      f"{'pred':>6}{'true':>6}{'bad':>9}")
out = {}
for m in order:
    r = fits[m]
    ch = reject.compare(r.p_bad(hold), hold["truth"], hold["outcome"])
    co = reject.compare(r.p_bad(oot), oot["truth"], oot["outcome"])
    ap = reject.approve_best(r.p_bad(hold), hold["truth"], share)
    out[m] = {"gini_hold": ch["gini"], "gini_oot": co["gini"],
              "dec_pred": ch["declined_predicted"],
              "dec_true": ch["declined_actual"],
              "bk_pred": ch["booked_predicted"],
              "bk_true": ch["booked_actual"], "approve_bad": ap}
    print(f"{m:<17}{ch['gini']:>6.3f}{co['gini']:>6.3f}"
          f"{ch['declined_predicted']:>6.1%}"
          f"{ch['declined_actual']:>6.1%}"
          f"{ch['booked_predicted']:>6.1%}{ch['booked_actual']:>6.1%}"
          f"{ap:>9.2%}")
m1h, m1o = hold["mark1_score"], oot["mark1_score"]
ap1 = reject.approve_best(-m1h, hold["truth"], share)
print(f"{'Mark I score':<17}"
      f"{metrics.gini(m1h, hold['truth'].astype(int)):>6.3f}"
      f"{metrics.gini(m1o, oot['truth'].astype(int)):>6.3f}"
      f"{'-':>6}{'-':>6}{'-':>6}{'-':>6}{ap1:>9.2%}")

print()
print("Gini gain over ignore, holdout, paired bootstrap (1,000 draws)")
rng = np.random.default_rng(SEED)
y = hold["truth"].to_numpy().astype(int)
base = -fits["ignore"].p_bad(hold).to_numpy()
for m in ("parcelling", "bureau retro", "truth (ceiling)"):
    alt = -fits[m].p_bad(hold).to_numpy()
    draws = metrics.bootstrap(
        lambda x1, x2, b: metrics.gini(x2, b) - metrics.gini(x1, b),
        base, alt, y, n=1000, rng=rng)
    lo, hi = metrics.interval(draws)
    g = out[m]["gini_hold"] - out["ignore"]["gini_hold"]
    print(f"  {m:<17}{g:>+7.3f}   {lo:+.3f} to {hi:+.3f}")
    out[m]["gain"] = [g, lo, hi]
out["_fernhill"] = {"share": share, "approve_bad": fern,
                    "mark1_approve_bad": ap1}
(ROOT / "code" / "09" / "08_methods_against_truth.json").write_text(
    json.dumps(out, indent=1) + "\n")
