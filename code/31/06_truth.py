# Checking the decomposition's "chance" against the answer: the true
# 12-month PD the simulator gave every performing personal loan at each
# year end, against the defaults that followed. Fernhill never has this.
import fernhill

con = fernhill.connect()
truth = fernhill.connect(truth=True)
true = truth.execute("""
    SELECT account_id, month, pd12 FROM pd12
    WHERE month(month) = 12 AND account_id LIKE 'PL%'
    ORDER BY account_id, month""").df()
# a loan's opening month has two rows, at opening and at the month
# end; the two are averaged
true = true.groupby(["account_id", "month"],
                    as_index=False)["pd12"].mean()
seen = con.execute("""
    WITH base AS (
        SELECT account_id, month, balance_cents FROM performance
        WHERE product = 'personal' AND month(month) = 12
          AND status IN ('up_to_date', 'arrears') AND missed <= 2),
    ahead AS (
        SELECT b.account_id, b.month, max(p.missed >= 3)::INT AS d
        FROM base b JOIN performance p
          ON p.account_id = b.account_id AND p.month > b.month
         AND p.month <= b.month + INTERVAL 12 MONTH
        GROUP BY 1, 2)
    SELECT b.*, coalesce(a.d, 0) AS d
    FROM base b LEFT JOIN ahead a USING (account_id, month)
    ORDER BY account_id, month""").df()
d = seen.merge(true, on=["account_id", "month"], validate="1:1")
d["year"] = d["month"].dt.year + 1
d["exp_c"] = d["pd12"] * d["balance_cents"]
d["seen_c"] = d["d"] * d["balance_cents"]
t = d[d["year"].between(2021, 2025)].groupby("year").agg(
    loans=("d", "size"), exp=("pd12", "sum"), seen=("d", "sum"),
    exp_c=("exp_c", "sum"), seen_c=("seen_c", "sum"))

print("personal loans performing on 1 January: defaults (three missed")
print("payments) in the year that followed")
print(f"{'':<6}{'loans':>7}{'true':>8}{'seen':>6}{'ratio':>7}"
      f"{'true, $':>12}{'seen, $':>12}{'luck, $':>10}")
for y, r in t.iterrows():
    print(f"{y:<6}{int(r.loans):>7,}{r.exp:>8.1f}{int(r.seen):>6}"
          f"{r.seen / r.exp:>7.2f}{r.exp_c / 100:>12,.0f}"
          f"{r.seen_c / 100:>12,.0f}"
          f"{(r.seen_c - r.exp_c) / 100:>+10,.0f}")
a, b = t.loc[2024], t.loc[2025]
print(f"\n2024 to 2025, balance falling into default: "
      f"{(b.seen_c - a.seen_c) / 100:+,.0f}")
print("  of which the true risk:  "
      f"{(b.exp_c - a.exp_c) / 100:>+10,.0f}")
print(f"  of which luck:           "
      f"{(b.seen_c - b.exp_c - a.seen_c + a.exp_c) / 100:>+10,.0f}")
