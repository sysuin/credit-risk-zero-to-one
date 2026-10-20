# Meridian's request, and the four years of accounts that came with it.
import textwrap

import fernhill

con = fernhill.connect()
rid, cid, when, kind, amount, tenor, purpose = con.execute("""
    SELECT request_id, company_id, request_date, facility,
           amount_cents, tenor_months, purpose
    FROM credit_requests WHERE request_id = 'R2025-117'""").fetchone()
name, sector, listed = con.execute("""
    SELECT name, sector, listed FROM companies
    WHERE company_id = ?""", [cid]).fetchone()
print(f"{rid}, received {when}")
print(f"  {name} ({cid}, {sector}, "
      f"{'listed' if listed else 'private'})")
print(f"  ${amount / 100:,.0f} {kind}, {tenor} months")
for line in textwrap.wrap(purpose, 60):
    print(f"  {line}")

rows = con.execute("""
    SELECT fiscal_year, basis, revenue_cents, net_income_cents,
           receivables_cents, cash_cents
    FROM financials WHERE company_id = ?
    ORDER BY fiscal_year""", [cid]).fetchall()
print(f"\n{'$000':<6}{'basis':<12}{'revenue':>10}{'profit':>9}"
      f"{'receivable':>12}{'cash':>8}")
for fy, basis, rev, net, recv, cash in rows:
    print(f"{fy:<6}{basis:<12}{rev / 1e5:>10,.0f}{net / 1e5:>9,.0f}"
          f"{recv / 1e5:>12,.0f}{cash / 1e5:>8,.0f}")
first, last = rows[0], rows[-1]
print(f"\n2025 against 2022: revenue x{last[2] / first[2]:.2f}, "
      f"receivables x{last[4] / first[4]:.2f}, "
      f"cash x{last[5] / first[5]:.2f}")
