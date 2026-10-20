# Ballast v0.4 decides every personal-loan application of 2025 and is
# set beside what Fernhill decided for the same people.
import fernhill
from ballast import data
from ballast.decision import engine
from ballast.decision import policy as pol

p = pol.Policy(champion="Mark II-R", source="reject/mark2_retro_ws",
               cutoff=554, refer_below=4, refer_above=4, dti_limit=0.50)
path = pol.save_policy(p)
assert pol.load_policy() == p
print(f"Saved {path.relative_to(path.parents[2])}")
print(f"  {p.champion}, cut-off {p.cutoff}, refer "
      f"{p.cutoff - p.refer_below}-{p.cutoff + p.refer_above - 1}")

con = fernhill.connect()
raw = data.load_applications(con, unknowns=False)
apps = raw[raw["product"].astype(str).eq("personal")
           & (raw["app_date"].astype(str) >= "2025-01-01")]
card = engine.load_champion(p)
d = engine.decide_all(apps, p, card)
d.assign(reasons=d["reasons"].map("; ".join)).to_parquet(
    pol.DECISION / "decisions_2025.parquet", index=False)

fern = apps["decision"].astype(str)
fraud = apps["decline_reason"].astype(object).eq("fraud_check")
print(f"\n{len(d):,} applications in 2025; Fernhill declined "
      f"{int(fraud.sum())} at its fraud checks")
print(f"  {'Ballast':<18}{'all':>7}{'Fernhill yes':>14}"
      f"{'Fernhill no':>13}")
for (dec, stage), g in d.groupby(["decision", "stage"]):
    yes = int((fern[g.index] == "approve").sum())
    print(f"  {dec + ', ' + stage:<18}{len(g):>7,}{yes:>14,}"
          f"{len(g) - yes:>13,}")

top = d.loc[d["stage"].eq("score") & d["decision"].ne("approve"),
            "reasons"].str[0]
print("\nFirst reason given, score declines and referrals")
for r, n in top.value_counts().head(4).items():
    print(f"  {r:<24}{n:>6,}  {engine.reason_text((r,))[0]}")

late = con.execute("""
    SELECT a.app_id, max(p.missed) AS worst
    FROM accounts a JOIN performance p USING (account_id)
    WHERE a.product = 'personal' AND a.open_date >= DATE '2025-01-01'
    GROUP BY 1 ORDER BY 1""").df()
b = d.merge(late, on="app_id")
print("\nLoans Fernhill booked in 2025, payments missed by December")
for name, g in (("Ballast approves", b[b["decision"] == "approve"]),
                ("Ballast refers", b[b["decision"] == "refer"]),
                ("Ballast declines", b[b["decision"] == "decline"])):
    print(f"  {name:<18}{len(g):>6,} loans, one or more missed "
          f"{(g['worst'] >= 1).mean():>6.1%}")
