# The two applications the complaint is about, side by side: what
# each said, what the bureau said, and how Mark I scored them.
from ballast import data
from ballast.decision import policy as pol

HERS, HIS = "A00073784", "A00073985"
raw = data.load_applications(unknowns=False)
two = raw.set_index("app_id").loc[[HERS, HIS]]

SHOW = [("applied", "app_date", "{}"), ("channel", "channel", "{}"),
        ("asked for", "amount_requested_cents", "${:,.0f}"),
        ("stated income", "stated_income_cents", "${:,.0f}"),
        ("age", "age", "{}"), ("time at address", "address_months",
                              "{} months"),
        ("bureau score", "bureau_score", "{}"),
        ("card utilisation", "revolving_utilisation", "{:.0%}"),
        ("worst status, 2 yrs", "worst_status_24m", "{} days")]
print(f"{'':<22}{'hers':>16}{'his':>16}")
for label, col, fmt in SHOW:
    vals = [two.loc[a, col] for a in (HERS, HIS)]
    if col.endswith("_cents"):
        vals = [v / 100 for v in vals]
    print(f"{label:<22}" + "".join(f"{fmt.format(v):>16}"
                                   for v in vals))

lines = pol.mark1_lines(two.reset_index())
print(f"\nMark I, line by line (base {pol.MARK1_BASE})")
for name in lines.columns:
    a, b = lines[name]
    flag = "   <- differs" if a != b else ""
    print(f"  {name:<20}{a:>16}{b:>16}{flag}")
print(f"  {'score':<20}" + "".join(f"{two.loc[a, 'mark1_score']:>16}"
                                   for a in (HERS, HIS)))
for a, who in ((HERS, "hers"), (HIS, "his")):
    r = two.loc[a]
    why = r["decline_reason"] if r["decision"] == "decline" else "-"
    print(f"{who}: cut-off {r['cutoff']}, {r['decision']}, "
          f"recorded reason: {why}")
