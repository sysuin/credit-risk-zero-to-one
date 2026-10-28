# Do Fernhill's defaults cluster? Each segment's yearly default rate
# against the spread it would show if borrowers defaulted alone.
import fernhill
import numpy as np
from ballast import portfolio as pf

con = fernhill.connect()
history = pf.default_history(con)     # one row per segment and year
print(f"{'segment':<14}{'years':>6}{'at risk':>9}{'rate':>7}"
      f"{'sd seen':>9}{'if alone':>10}{'ratio':>7}")
for seg in pf.SEGMENTS + ["sme_emergency"]:
    rows = history[history.segment == seg]
    # The spread actually seen in the yearly default rate.
    seen = rows.rate.std(ddof=1)
    # The spread chance alone would give: binomial noise each year.
    noise = rows.rate * (1 - rows.rate) / rows.at_risk
    alone = np.sqrt(noise.mean())
    print(f"{seg:<14}{len(rows):>6}{rows.at_risk.mean():>9,.0f}"
          f"{rows.rate.mean():>7.2%}{seen:>9.2%}{alone:>10.2%}"
          f"{seen / alone:>7.1f}")

companies = history[history.segment == "companies"]
counts = " ".join(str(d) for d in companies.defaults)
print("\ncompanies' defaults by year, 2017-2025: " + counts)
print(f"  {companies.defaults.sum()} in "
      f"{companies.at_risk.sum():,} client-years")
