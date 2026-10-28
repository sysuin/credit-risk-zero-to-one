# Why three missed payments, and why twelve months: what came next.
import fernhill
from ballast.scorecard import sample

con = fernhill.connect()
out = sample.outcomes(con)
dates = con.execute("""
    SELECT a.app_id, a.app_date, c.close_reason
    FROM applications a JOIN accounts c USING (account_id)
    WHERE a.product = 'personal'""").df()
out = out.merge(dates, on="app_id")
dev = out[sample.period(out["app_date"].dt.date) == "development"]
dev = dev.assign(worst=dev["worst_missed"].clip(upper=6))

print("development loans by the most payments missed at once in")
print("their first 12, and how each loan had ended by December 2025")
print(f"{'missed':<8}{'loans':>7}{'charged off':>13}{'paid off':>10}"
      f"{'open':>7}")
for k, g in dev.groupby("worst"):
    co = (g["close_reason"] == "charged_off").mean()
    paid = g["close_reason"].isin(["repaid", "prepaid"]).mean()
    still = g["close_reason"].isna().mean()
    label = "6+" if k == 6 else str(k)
    print(f"{label:<8}{len(g):>7,}{co:>13.1%}{paid:>10.1%}"
          f"{still:>7.1%}")

# When do loans first reach three missed? Loans opened 2016-2021,
# each followed for 24 months.
first = con.execute("""
    SELECT min(datediff('month', c.open_date, p.month)) AS mob
    FROM accounts c JOIN performance p USING (account_id)
    WHERE c.product = 'personal' AND c.open_date < DATE '2022-01-01'
      AND p.missed >= 3
      AND datediff('month', c.open_date, p.month) BETWEEN 1 AND 24
    GROUP BY c.account_id
""").df()["mob"]
print()
print("loans opened 2016-2021 that reached three missed within 24")
print(f"months: {len(first):,}; share that had done so by month")
line = ""
for month in (6, 9, 12, 18, 24):
    line += f"  {month:>2}: {(first <= month).mean():.0%}"
print(line)
