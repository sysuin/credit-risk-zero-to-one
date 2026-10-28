# Fernhill's commercial margins against the risk it knew when each
# facility was signed: grade, security, outcome, and the ratios.
import fernhill
from _book import accounts, latest_year
from ballast.commercial import structure as st

con = fernhill.connect()
# Each facility with its margin, security, whether the borrower later
# defaulted, and the latest internal grade on or before signing.
f = con.execute("""
    SELECT f.company_id, f.start_date, f.margin_bps, f.secured,
           d.company_id IS NOT NULL AS dflt,
           (SELECT r.internal_grade FROM ratings r
            WHERE r.company_id = f.company_id
              AND r.internal_grade IS NOT NULL
              AND r.rating_date <= f.start_date
            ORDER BY r.rating_date DESC LIMIT 1) AS grade
    FROM facilities f LEFT JOIN corporate_defaults d USING (company_id)
    ORDER BY f.facility_id""").df()
print(f"margins from {f.margin_bps.min()} to {f.margin_bps.max()} "
      f"bps; at the {f.margin_bps.min()} floor: "
      f"{(f.margin_bps == f.margin_bps.min()).mean():.0%}")

groups = [("grades 1-3 (safest)", f.grade <= 3),
          ("grades 4-6", f.grade.between(4, 6)),
          ("grades 7-10", f.grade >= 7),
          ("no grade yet", f.grade.isna()),
          ("secured", f.secured), ("unsecured", ~f.secured),
          ("borrower later defaulted", f.dflt),
          ("borrower never defaulted", ~f.dflt)]
print(f"\n{'':<30}{'facilities':>10}{'mean margin':>14}")
for label, mask in groups:
    print(f"  {label:<28}{mask.sum():>10}"
          f"{f.margin_bps[mask].mean():>14.0f}")
rho = f.grade.corr(f.margin_bps)
print(f"correlation of grade at signing and margin: {rho:+.2f}")

# Borrowers whose accounts at signing looked like Meridian's.
f["fy"] = f.start_date.dt.date.map(latest_year)
signed = f.merge(accounts(con), on=["company_id", "fy"])
ratios = st.breaches(signed.debt, signed.ebitda, signed.interest,
                     1.0, 1.0)
like = signed[ratios.leverage.between(1.5, 3.0)
              & (ratios.cover >= 5)]
q = like.margin_bps.quantile([0.25, 0.5, 0.75])
print(f"\nsigned at 1.5x-3.0x leverage and 5x+ cover: {len(like)}")
print(f"  margin p25 {q[0.25]:.0f}, median {q[0.5]:.0f}, "
      f"p75 {q[0.75]:.0f} bps")
