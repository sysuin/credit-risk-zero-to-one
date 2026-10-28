# Loss given default in bad years: retail on a line through Chapter
# 19's long-run and downturn LGDs; companies by Frye and Jacobs' rule.
import fernhill
from ballast import capital, portfolio as pf
from ballast.commercial import rating
from scipy.stats import norm

con = fernhill.connect()
est = pf.load_json("correlations.json")
pools, names = pf.book(con, capital.load())
# How bad a year is: the share of years that are better than it.
years = [("median", 0.5), ("1 in 10", 0.9), ("1 in 100", 0.99),
         ("1 in 1,000", 0.999)]
print(f"{'LGD in a year that is':<22}"
      + "".join(f"{k:>11}" for k, _ in years))
for p in ("personal", "card", "auto", "sme_term"):
    row = pools[pools["product"] == p].iloc[0]
    # The line holds for loans that do not cure, so divide by the
    # share that do not cure, then scale back.
    stay = 1 - row.cure_rate
    lg = [stay * pf.lgd_in_draw(row.lgd / stay, row.downturn / stay,
                                -norm.ppf(q)) for _, q in years]
    print(f"{p:<22}" + "".join(f"{v:>11.1%}" for v in lg))

# Companies: the long-run LGD weighted by exposure, at three grades.
lgd = (names.lgd * names.ead).sum() / names.ead.sum()
rho = est["companies"]["rho"]
for g in (4, 7, 9):
    lg = [pf.frye_jacobs(rating.pd_of(g), lgd, rho, -norm.ppf(q))
          for _, q in years]
    print(f"{f'company, grade {g}':<22}"
          + "".join(f"{v:>11.1%}" for v in lg))
