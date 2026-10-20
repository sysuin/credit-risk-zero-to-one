# Exercise 27.1: the capital target with other management buffers.
import fernhill
from ballast import appetite as ap
from ballast import stress

con = fernhill.connect()
cap = ap.capital_now(con)
s = stress.load()["summary"]
print(f"CET1 ratio today {cap['cet1_ratio']:.2%}")
print(f"{'buffer':>7}{'target':>9}{'CET1 above it':>16}")
for b in (0.005, 0.01, 0.015, 0.02):
    t = ap.capital_target(cap, s, buffer=b)["target"]
    over = cap["cet1"] - t * cap["sa_rwa"]
    print(f"{b:>7.1%}{t:>9.1%}{over / 1e8:>15,.1f}m")
drop = cap["cet1_ratio"] - cap["requirement"] - \
    (s["year_zero"]["cet1_sa"] - s["trough_sa"]["severe"])
print(f"Fernhill is below its target for any buffer above {drop:.2%}")
