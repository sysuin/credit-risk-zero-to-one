# Meridian against Fernhill's wholesale clients: each ratio's place
# among the peers' latest audited year, and how far each has moved.
import json

import fernhill
from ballast.commercial import spreading as sp
from ballast.config import ROOT

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
latest = con.execute("""
    SELECT max(fiscal_year) FROM financials
    WHERE basis = 'audited' AND company_id <> ?""", [m]).fetchone()[0]
peers = sp.peer_ratios(con, "wholesale", latest, exclude=[m])
r = sp.ratios(sp.spread(sp.accounts(con, m)))
show = [("ebitda_margin", "EBITDA margin", "%"),
        ("leverage", "debt / EBITDA", "x"),
        ("interest_cover", "EBITDA / interest", "x"),
        ("current_ratio", "current ratio", "x"),
        ("equity_ratio", "equity / assets", "%"),
        ("receivable_days", "receivable days", "d"),
        ("inventory_days", "inventory days", "d"),
        ("payable_days", "payable days", "d"),
        ("cash_cycle", "cash cycle", "d"),
        ("cash_conversion", "OCF / EBITDA", "%"),
        ("cash_days", "cash, days of costs", "d"),
        ("payout", "dividend payout", "%")]
names = [k for k, _, _ in show]
c24 = sp.compare(r[latest], peers, names)
c25 = sp.compare(r[2025], peers, names)
print(f"{len(peers)} wholesale clients, fiscal {latest}; "
      f"Meridian {latest} and 2025")


def fmt(v, unit):
    # A share, a multiple, or a number of days.
    if unit == "%":
        return f"{v:.0%}"
    if unit == "x":
        return f"{v:.1f}x"
    return f"{v:.0f}"


print(f"{'':<20}{'p25':>7}{'median':>7}{'p75':>7}{'M 2024':>8}"
      f"{'M 2025':>8}{'below':>7}")
for key, label, unit in show:
    a, b = c24.loc[key], c25.loc[key]
    print(f"{label:<20}{fmt(a.p25, unit):>7}"
          f"{fmt(a['median'], unit):>7}{fmt(a.p75, unit):>7}"
          f"{fmt(a.value, unit):>8}{fmt(b.value, unit):>8}"
          f"{b.share_below:>7.0%}")
print("below: share of peers below Meridian's 2025 value")

first = latest - 2
before = sp.peer_ratios(con, "wholesale", first, exclude=[m])
print(f"\nchange in days, {first} to {latest} "
      f"({len(before.index.intersection(peers.index))} peers in both)")
print(f"{'':<20}{'Meridian':>9}{'median':>8}{'largest rise':>14}")
moves = {}
for key, label in [("receivable_days", "receivable days"),
                   ("cash_cycle", "cash cycle")]:
    move = (peers[key] - before[key]).dropna()
    mine = r.loc[key, latest] - r.loc[key, first]
    moves[key] = sorted(round(float(v), 2) for v in move)
    print(f"{label:<20}{mine:>+9.1f}{move.median():>+8.1f}"
          f"{move.max():>+14.1f}")

acc = sp.peer_accounts(con, "wholesale", latest, exclude=[m])
print(f"\npeers with negative equity: {(acc.equity < 0).sum()}; "
      f"debt / EBITDA above 10x: {(peers.leverage > 10).sum()}")

json.dump({"year": int(latest), "n": len(peers),
           "ratios": [[k, label, unit] for k, label, unit in show],
           "peers": {k: sorted(round(float(v), 4)
                               for v in peers[k].dropna())
                     for k in names},
           "m2024": {k: round(float(r.loc[k, 2024]), 4)
                     for k in names},
           "m2025": {k: round(float(r.loc[k, 2025]), 4)
                     for k in names},
           "moves": moves},
          open(ROOT / "code/14/12_peers.json", "w"))
