# Exercise 19.4: card CCFs on a six-month horizon against twelve.
import fernhill
from ballast.parameters import ead

con = fernhill.connect()
fits = {}
for h in (6, 12):
    s = ead.ccf_sample(con, "card", horizon=h)
    s = s[s["missed0"] == 0]
    fits[h] = (len(s), ead.fit_ccf(s), ead.pooled_ccf(s))
print(f"{'used then':<12}{'6 months':>10}{'12 months':>11}")
for band in fits[12][1].index:
    print(f"{band:<12}{fits[6][1].loc[band, 'ccf_raw']:>10.2f}"
          f"{fits[12][1].loc[band, 'ccf_raw']:>11.2f}")
print(f"{'all':<12}{fits[6][2]:>10.2f}{fits[12][2]:>11.2f}")
print(f"{'defaults':<12}{fits[6][0]:>10,}{fits[12][0]:>11,}")
