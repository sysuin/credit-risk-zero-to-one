# The foundation approach's supervisory LGD and conversion factor for
# companies, against what Fernhill's own commercial history says.
import fernhill
import numpy as np
from ballast import capital, ecl
from ballast.parameters import ead as eadm

con = fernhill.connect()
r = capital.load()
w = ecl.commercial_lgd(con)          # Chapter 20's commercial workouts
own = {k: (g.lgd * g.ead_cents).sum() / g.ead_cents.sum()
       for k, g in w.groupby("secured")}
ccf = eadm.load()["ccf"]["revolver"]
print(f"commercial workouts: {len(w)}; LGD secured {own[True]:.1%}, "
      f"unsecured {own[False]:.1%}")
print(f"supervisory LGD {capital.FIRB_LGD:.0%}; revolver CCF: "
      f"supervisory {capital.FIRB_CCF:.0%}, Fernhill's {ccf:.2f}")
c = r[r.segment == "commercial"].copy()
lgd = np.where(c.secured.astype(bool), own[True], own[False])
runs = {"supervisory": capital.irb(c),
        "own CCF": capital.irb(c, revolver_ccf=ccf),
        "own LGD": capital.irb(c, corporate_lgd=lgd),
        "own LGD and CCF": capital.irb(c, corporate_lgd=lgd,
                                       revolver_ccf=ccf)}
print(f"\n{'companies':<18}{'EAD $m':>9}{'RWA $m':>9}{'density':>9}"
      f"{'EL $m':>8}")
for k, x in runs.items():
    print(f"{k:<18}{x.irb_ead.sum() / 1e8:>9,.0f}"
          f"{x.irb_rwa.sum() / 1e8:>9,.0f}"
          f"{x.irb_rwa.sum() / x.irb_ead.sum():>9.0%}"
          f"{x.el.sum() / 1e8:>8,.1f}")
print(f"{'standardised':<18}{c.sa_ead.sum() / 1e8:>9,.0f}"
      f"{c.sa_rwa.sum() / 1e8:>9,.0f}"
      f"{c.sa_rwa.sum() / c.sa_ead.sum():>9.0%}")
