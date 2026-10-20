# One account's provision worked month by month: a personal loan one
# payment behind on 31 December 2025, in the base scenario.
# timeout: 300
import json
from pathlib import Path

import fernhill
import numpy as np
from ballast import ecl

con = fernhill.connect()
params = ecl.parameters(con)
book = ecl.retail_book(con)
behind = book[(book["product"] == "personal") & (book["missed"] == 1)]
behind = behind.sort_values(["balance_cents", "account_id"])
a = behind.iloc[len(behind) // 2]            # the median balance

n = int(a["remaining"])
k = np.arange(1, n + 1)
model = params["hazards"]["personal"]
u = ecl.path(params["scenarios"].loc["base", "path"], n)
h = ecl.hazards(model, a["mob"] + k[None, :], [a["band"]], u)
x = np.full((1, n), params["prepay"]["personal"])
pd12 = ecl.incidence(h[:, :12], x[:, :12]).sum()
lift = params["uplift"].loc[("personal", "30"), "uplift"]
h = ecl.lift(h, x, np.array([min(pd12 * lift, 0.99)]))
marg = ecl.incidence(h, x)[0]
alive = marg / h[0]
ead = ecl.balances([a["balance_cents"]], [a["rate_pct"]], [n], n)[0]
df = (1 + a["rate_pct"] / 1200) ** -k
lgd = params["lgd"].loc["personal", "lgd"]
loss = marg * ead * df * lgd

print(f"{a['account_id']}: band {a['band']}, {a['mob']} months on "
      f"book, {n} to go, {a['rate_pct']:.2f}%")
print(f"balance ${a['balance_cents'] / 100:,.2f}; one payment missed;"
      f" LGD {lgd:.1%}")
print(f"12-month PD of its band {pd12:.2%}, times {lift:.1f} for the "
      f"'30' pool")
print(f"\n{'month':>5}{'hazard':>9}{'alive':>8}{'marginal':>10}"
      f"{'EAD':>11}{'discount':>9}{'loss':>9}")
for m in sorted({1, 2, 3, 6, 12, 13, 24, 36, n} & set(k)):
    i = m - 1
    print(f"{m:>5}{h[0, i]:>9.4f}{alive[i]:>8.3f}{marg[i]:>10.4f}"
          f"{ead[i] / 100:>11,.2f}{df[i]:>9.4f}{loss[i] / 100:>9.2f}")
print(f"\n12 months: PD {marg[:12].sum():.2%}, ECL "
      f"${loss[:12].sum() / 100:,.2f}")
print(f"lifetime:  PD {marg.sum():.2%}, ECL ${loss.sum() / 100:,.2f}"
      f" (stage 2 books this)")
Path(__file__).with_suffix(".json").write_text(json.dumps({
    "account": a["account_id"], "balance": float(a["balance_cents"]),
    "marginal": marg.round(6).tolist(),
    "ead": (ead / 100).round(2).tolist(),
    "loss": (loss / 100).round(4).tolist()}) + "\n")
