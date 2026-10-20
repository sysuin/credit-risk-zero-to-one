# What protection on one commercial client would cost: Elm Juniper
# Foods, its CDS quotes in 2025, and a hedge on part of the exposure.
import fernhill
from ballast import securitisation as sec
from ballast.commercial.rating import pd_of
from ballast.config import AS_OF

NOTIONAL = 20_000_000_00      # cents: protection on $20m, five years
con = fernhill.connect()
cid, name = con.execute("SELECT company_id, name FROM companies "
                        "WHERE name = 'Elm Juniper Foods'").fetchone()
q = con.execute("""SELECT month, cds_5y_bps FROM market_data
                   WHERE company_id = ? AND year(month) = 2025
                   ORDER BY month""", [cid]).fetchall()
print(f"{name} ({cid}), five-year CDS in 2025, basis points")
for i in (0, 6):
    print("  " + "".join(f"{m:%b}{s:>6.0f}  " for m, s in q[i:i + 6])
          .rstrip())
fac = con.execute("""
    SELECT f.facility_id, f.kind, f.maturity_date, f.margin_bps,
           f.secured, m.drawn_cents
    FROM facilities f JOIN facility_months m USING (facility_id)
    WHERE f.company_id = ? AND m.month = ?
    ORDER BY f.facility_id""", [cid, AS_OF]).fetchall()
print("\nFernhill's facilities on 31 December 2025")
for fid, kind, mat, margin, secured, drawn in fac:
    print(f"  {fid:<12}{kind:<9}{mat:%b %Y}  {margin} bp  "
          f"drawn ${drawn / 100:,.0f}")
grade = con.execute("""SELECT internal_grade FROM ratings
                       WHERE company_id = ? AND internal_grade IS NOT
                       NULL ORDER BY rating_date DESC LIMIT 1""",
                    [cid]).fetchone()[0]
spread = q[-1][1]
c = sec.cds_cost(NOTIONAL, spread)
earned = NOTIONAL * max(f[3] for f in fac) / 1e4
print(f"\nprotection on ${NOTIONAL / 100:,.0f} at {spread:.1f} bp:")
print(f"  premium ${c['premium_a_year'] / 100:,.0f} a year, "
      f"${c['premium_total'] / 100:,.0f} over five years")
print(f"  pays ${c['payout_if_default'] / 100:,.0f} if Elm Juniper "
      "defaults (40% recovery)")
print(f"  the loans' best margin earns ${earned / 100:,.0f} a year "
      f"on ${NOTIONAL / 100:,.0f}")
print(f"  market's one-year PD {c['pd_1y']:.2%}; Fernhill's grade "
      f"{grade:.0f}, PD {pd_of(int(grade)):.2%}")
