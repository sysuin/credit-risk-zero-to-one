# PSI and information value are the same divergence, measured twice.
import numpy as np

import fernhill
from ballast import monitoring
from ballast.scorecard import sample, woe


def kl(p, q):
    """Kullback-Leibler divergence of shares p from shares q."""
    return float((p * np.log(p / q)).sum())


con = fernhill.connect()
half = con.execute("""
    SELECT year(app_date) || CASE WHEN month(app_date) <= 6
                                  THEN ' H1' ELSE ' H2' END AS half,
           list(bureau_score ORDER BY app_id) AS scores
    FROM applications
    WHERE bureau_hit AND year(app_date) IN (2018, 2019)
    GROUP BY ALL ORDER BY ALL""").fetchall()
scores = {h: np.array(v, dtype=float) for h, v in half}

print(f"{'reference':<10}{'compared':<10}{'n':>7}{'PSI':>8}"
      f"{'KL + KL':>9}{'noise 99%':>11}")
for ref, act in (("2018 H1", "2018 H2"), ("2019 H1", "2019 H2")):
    e_s, a_s = scores[ref], scores[act]
    edges = monitoring.decile_edges(e_s)
    e = monitoring.shares(e_s, edges)
    a = monitoring.shares(a_s, edges)
    print(f"{ref:<10}{act:<10}{len(a_s):>7,}"
          f"{monitoring.psi(e_s, a_s):>8.4f}{kl(a, e) + kl(e, a):>9.4f}"
          f"{monitoring.psi_noise(len(a_s), len(e_s)):>11.4f}")

# Information value: the same divergence, goods against bads.
s = sample.load_sample()
train = s[s["fit"]]
binset = woe.load_binset(sample.MARK2 / "bins.json")
print(f"\n{'characteristic':<24}{'IV':>8}{'KL + KL':>9}")
for name in ("bureau_score", "enquiries_6m", "region"):
    t = woe.woe_table(binset[name], train[name], train["bad"])
    t = t[t["n"] > 0]
    g, b = t["pct_good"].to_numpy(), t["pct_bad"].to_numpy()
    iv = woe.information_value(binset[name], train[name], train["bad"])
    print(f"{name:<24}{iv:>8.4f}{kl(g, b) + kl(b, g):>9.4f}")
