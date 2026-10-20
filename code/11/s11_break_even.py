# Exercise 11.3: how the break-even and the chosen cut-off move with
# the running cost assumed.
import fernhill
from ballast.decision import strategy
from ballast.scorecard import points, reject, sample

con = fernhill.connect()
s = sample.load_sample()
s = s[s["app_date"].astype(str).between("2019-01-01", "2021-12-31")]
a = reject.frames(reject.applicants())["oot"]
score = reject.load_refit("mark2_retro_ws").scorecard().score(a)
p = points.bad_rate_at(score)
c = strategy.curve(score, p, range(530, 601))
today = float(p[a["outcome"].ne("declined").to_numpy()].mean())
print(f"{'running cost':>13}{'good earns':>12}{'bad costs':>11}"
      f"{'break-even':>12}{'cut-off':>9}")
for opex in (1.5, 2.5, 3.5):
    eco = strategy.loan_economics(con, "personal", opex_pct=opex)
    d = s[["account_id", "outcome"]].merge(eco, on="account_id")
    good = d.loc[d["outcome"] == "good", "profit"].mean()
    bad = -d.loc[d["outcome"] == "bad", "profit"].mean()
    _, even = strategy.break_even(good, bad)
    try:
        cut = strategy.choose_cutoff(c, today, 2 / 3 * even)
    except ValueError:
        cut = "none"
    print(f"{opex:>12.1f}%{good / 100:>12,.0f}{bad / 100:>11,.0f}"
          f"{even:>12.1%}{cut:>9}")
