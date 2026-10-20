# Early-warning signals for commercial clients, each measured on its
# record: Mar 2017 to Dec 2024, every month end, a year to see.
import fernhill
from ballast import monitoring as mon

con = fernhill.connect()
p = mon.business_panel(con)
known = p[p["default_12m"].notna()]
print(f"{len(known):,} company-months on {known.company_id.nunique()} "
      f"clients; {known.default_12m.mean():.2%} followed by a default")
print(f"within {mon.HORIZON} months; "
      f"{int(known.groupby('company_id').default_12m.max().sum())} "
      f"clients defaulted")
r = mon.watch_record(p, mon.watch(p))
print(f"\n{'trigger':<13}{'months':>7}{'clients':>8}{'hit':>7}"
      f"{'caught':>8}{'false':>7}{'warning':>9}")
print(f"{'':<13}{'':>7}{'':>8}{'rate':>7}{'':>8}{'alarms':>7}"
      f"{'months':>9}")
for x in r.itertuples():
    print(f"{x.flag:<13}{x.months:>7,}{x.companies:>8}"
          f"{x.hit_rate:>7.1%}{x.caught:>5} of {x.defaults:<3}"
          f"{x.false_alarms:>4}{x.warning:>9.0f}")
for name, (text, _) in mon.TRIGGERS.items():
    print(f"  {name:<12} {text}")
