# Meridian's balance sheet at 31 December 2025, as the table holds it:
# what it owns, who has a claim on it, and the line it leaves out.
import fernhill

con = fernhill.connect()
(cash, recv, inv, ca, ta, cl, pay, debt, equity) = con.execute("""
    SELECT cash_cents, receivables_cents, inventory_cents,
           current_assets_cents, total_assets_cents,
           current_liabilities_cents, payables_cents,
           total_debt_cents, equity_cents
    FROM financials JOIN companies USING (company_id)
    WHERE name = 'Meridian Supply Co.' AND fiscal_year = 2025
    """).fetchone()


def show(label, cents):
    print(f"  {label:<44}{cents / 1e5:>9,.0f}")


print("WHAT MERIDIAN OWNS ($000)")
show("cash", cash)
show("receivables (customers owe it)", recv)
show("inventory (goods in the warehouse)", inv)
show("current assets", ca)
show("fixed and other assets (total - current)", ta - ca)
show("total assets", ta)
print("WHO HAS A CLAIM ON IT")
show("current liabilities (due within a year)", cl)
show("  of which trade payables (to suppliers)", pay)
show("borrowings (all of them)", debt)
show("equity (the owners' stake)", equity)
show("everything owed to others (assets - equity)", ta - equity)
show("current liabilities + borrowings", cl + debt)
due = cl + debt - (ta - equity)
show("so borrowings inside current liabilities", due)
show("and accruals (current - payables - those)", cl - pay - due)
