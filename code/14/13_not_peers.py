# The wholesale clients missing from the peer group: the two that
# defaulted, and what their last accounts before default looked like.
import fernhill
from ballast.commercial import spreading as sp

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
gone = con.execute("""
    SELECT d.company_id, d.default_month, d.kind,
           max(f.fiscal_year) AS last_year
    FROM corporate_defaults d
    JOIN companies c USING (company_id)
    JOIN financials f USING (company_id)
    WHERE c.sector = 'wholesale'
      AND f.fiscal_year < year(d.default_month)
    GROUP BY ALL ORDER BY d.default_month""").fetchall()
cols = [(m, 2025, "Meridian")]
for cid, month, kind, last in gone:
    print(f"{cid} defaulted {month}, {kind.replace('_', ' ')};")
    print(f"      last accounts before it: {last}")
    cols.append((cid, last, cid))

frames = {}
for cid, year, label in cols:
    s = sp.spread(sp.accounts(con, cid))
    r = sp.ratios(s)
    growth = s.loc["revenue", year] / s.loc["revenue", year - 3] - 1
    frames[label] = (s[year], r[year], growth)
print(f"\n{'':<24}" + "".join(f"{k:>10}" for k in frames))
rows = [("revenue, $m", lambda s, r, g: f"{s.revenue / 1e8:.0f}"),
        ("revenue, 3-year change", lambda s, r, g: f"{g:+.0%}"),
        ("debt / EBITDA", lambda s, r, g: f"{r.leverage:.1f}x"),
        ("EBITDA / interest",
         lambda s, r, g: f"{r.interest_cover:.1f}x"),
        ("current ratio", lambda s, r, g: f"{r.current_ratio:.2f}x"),
        ("receivable days", lambda s, r, g: f"{r.receivable_days:.0f}"),
        ("OCF / EBITDA", lambda s, r, g: f"{r.cash_conversion:.0%}")]
for label, fn in rows:
    print(f"{label:<24}" + "".join(f"{fn(*v):>10}"
                                   for v in frames.values()))
