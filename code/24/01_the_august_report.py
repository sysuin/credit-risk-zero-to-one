# The page Fernhill's monitoring report printed in August 2019: Mark I
# scores of July's personal-loan applicants against the year before.
import fernhill
from ballast import monitoring as mon

con = fernhill.connect()
a = con.execute("""
    SELECT app_date, mark1_score FROM applications
    WHERE product = 'personal'
      AND app_date BETWEEN '2018-07-01' AND '2019-07-31'
    ORDER BY app_id""").df()
day = a["app_date"].astype(str)
ref = a.loc[day < "2019-07-01", "mark1_score"]
july = a.loc[day >= "2019-07-01", "mark1_score"]
t = mon.psi_table(ref, july)
print("Mark I, personal-loan applicants: July 2019 against")
print(f"July 2018 - June 2019 ({len(july):,} against {len(ref):,})")
print(f"{'score band':<12}{'last year':>11}{'July':>8}{'PSI part':>10}")
for r in t.itertuples():
    print(f"{r.band:<12}{r.reference:>11.1%}{r.actual:>8.1%}"
          f"{r.part:>10.4f}")
total = mon.psi(ref, july)
print(f"{'PSI':<12}{total:>29.3f}   "
      f"{mon.light(total, mon.PSI_AMBER, mon.PSI_RED)}")
print(f"mean score {ref.mean():.1f} -> {july.mean():.1f}")
