# Every default episode as a workout: how each ended, and a check that
# every dollar in the recoveries table landed in exactly one of them.
import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)              # Chapter 6's episodes, stitched
f = lgd.cash_flows(con, w)

print(f"workouts (dod2021 episodes, stitched): {len(w):,}")
print(f"\n{'product':<15}{'cured':>7}{'paid':>6}{'written':>9}"
      f"{'open':>6}{'total':>7}")
tab = w.groupby(["product", "outcome"]).size().unstack(fill_value=0)
for p, r in tab.iterrows():
    print(f"{p:<15}{r['cured']:>7}{r['paid_off']:>6}"
          f"{r['written_off']:>9}{r['open']:>6}{r.sum():>7}")
t = tab.sum()
print(f"{'all':<15}{t['cured']:>7}{t['paid_off']:>6}"
      f"{t['written_off']:>9}{t['open']:>6}{t.sum():>7}")

table = con.execute("""SELECT count(*), sum(r.amount_cents)
    FROM recoveries r JOIN accounts a USING (account_id)""").fetchone()
mine = f[~f["kind"].isin(["payment", "cure"])]
print(f"\nrecoveries rows    {table[0]:>8,} rows "
      f"${table[1] / 100:>13,.2f}")
print(f"in the workouts    {len(mine):>8,} rows "
      f"${mine['amount_cents'].sum() / 100:>13,.2f}")
by_kind = f.groupby("kind")["amount_cents"].sum() / 100
print(f"payments in default        ${by_kind['payment']:>13,.2f}")
print(f"balances handed back cured ${by_kind['cure']:>13,.2f}")
print(f"\nworkouts with nothing owed at default: "
      f"{(w['ead_cents'] <= 0).sum()} (no LGD; left out)")
