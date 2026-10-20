# Exercise 24.2: Mark I on personal, card and car-loan applicants,
# 2016 to 2025: the mean each year and the PSI against 2016's
# applicants, starred where it exceeds its 99% noise level.
import fernhill
from ballast import monitoring as mon

con = fernhill.connect()
a = con.execute("""
    SELECT year(app_date) AS y, product, mark1_score FROM applications
    WHERE product IN ('personal', 'card', 'auto')
    ORDER BY app_id""").df()
PRODUCTS = ("personal", "card", "auto")
print(f"{'year':<6}" + "".join(f"{p:>20}" for p in PRODUCTS))
print(f"{'':<6}" + "".join(f"{'mean':>10}{'PSI 2016':>10}"
                           for _ in PRODUCTS))
for y in range(2017, 2026):
    cells = ""
    for p in PRODUCTS:
        s = a[a["product"] == p]
        ref, now = s[s.y == 2016].mark1_score, s[s.y == y].mark1_score
        v = mon.psi(ref, now)
        star = "*" if v >= mon.psi_noise(len(now), len(ref)) else " "
        cells += f"{now.mean():>10.1f}{v:>9.3f}{star}"
    print(f"{y:<6}{cells}")
levels = []
for p in PRODUCTS:
    n = a[(a["product"] == p) & (a.y == 2025)].shape[0]
    n16 = a[(a["product"] == p) & (a.y == 2016)].shape[0]
    levels.append(f"{p} {mon.psi_noise(n, n16):.3f}")
print("noise levels at 2025's volumes:")
print("  " + ", ".join(levels))
