# The wholesale clients missing from the peer group: the three that
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
# Format each company's column of the table.
columns = []
for year_accounts, year_ratios, growth in frames.values():
    columns.append([f"{year_accounts.revenue / 1e8:.0f}",
                    f"{growth:+.0%}",
                    f"{year_ratios.leverage:.1f}x",
                    f"{year_ratios.interest_cover:.1f}x",
                    f"{year_ratios.current_ratio:.2f}x",
                    f"{year_ratios.receivable_days:.0f}",
                    f"{year_ratios.cash_conversion:.0%}"])
labels = ["revenue, $m", "revenue, 3-year change", "debt / EBITDA",
          "EBITDA / interest", "current ratio", "receivable days",
          "OCF / EBITDA"]
for i, label in enumerate(labels):
    print(f"{label:<24}" + "".join(f"{col[i]:>10}" for col in columns))
