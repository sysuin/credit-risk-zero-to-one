# Open banking: when each channel began to collect consent, how many
# said yes, and where the bank-account fields are missing.
import json

import fernhill

con = fernhill.connect()
print("first consent, by channel:")
for ch, first, n in con.execute("""
    SELECT channel, min(app_date), count(*) FROM applications
    WHERE ob_consent GROUP BY channel ORDER BY min(app_date)
""").fetchall():
    print(f"  {ch:<8}{first}   {n:>7,} consents in all")
print("  broker and dealer: none")

print()
print("consent rate among applications made after it was offered")
print(f"{'year':<6}{'online':>9}{'branch':>9}")
for y, online, branch in con.execute("""
    SELECT year(app_date),
           avg(ob_consent::INT) FILTER (WHERE channel = 'online'
               AND app_date >= DATE '2021-03-01'),
           avg(ob_consent::INT) FILTER (WHERE channel = 'branch'
               AND app_date >= DATE '2023-01-01')
    FROM applications WHERE year(app_date) >= 2021
    GROUP BY ALL ORDER BY ALL
""").fetchall():
    b = f"{branch:>9.1%}" if branch is not None else f"{'-':>9}"
    print(f"{y:<6}{online:>9.1%}{b}")

total, yes, asked, together = con.execute("""
    SELECT count(*), count(*) FILTER (WHERE ob_consent),
           count(*) FILTER (WHERE
               (channel = 'online' AND app_date >= DATE '2021-03-01')
            OR (channel = 'branch' AND app_date >= DATE '2023-01-01')),
           count(*) FILTER (WHERE
               (ob_avg_balance_cents IS NULL)::INT
             + (ob_overdraft_days IS NULL)::INT
             + (ob_income_volatility IS NULL)::INT
             + (ob_returned_payments IS NULL)::INT
             + (ob_betting_share IS NULL)::INT IN (0, 5))
    FROM applications
""").fetchone()
print()
print(f"ob_consent true:              {yes:>8,} of {total:>8,}"
      f"  {yes / total:>6.1%}")
print(f"  of those asked:             {yes:>8,} of {asked:>8,}"
      f"  {yes / asked:>6.1%}")
print(f"rows whose five ob_ fields are all present or all missing: "
      f"{together:,}")

cells = con.execute("""
    SELECT channel, year(app_date) * 10 + (month(app_date) > 6)::INT,
           avg((ob_avg_balance_cents IS NOT NULL)::INT)
    FROM applications GROUP BY ALL ORDER BY ALL
""").fetchall()
with open("code/05/08_open_banking.json", "w") as f:
    json.dump([{"channel": c, "half": f"{h // 10}H{h % 10 + 1}",
                "present": p} for c, h, p in cells], f, indent=1)
