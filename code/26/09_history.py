# Two of the decade's episodes replayed on today's book: the 2020
# shock and the 2022-23 rise in rates, each as changes from today.
# timeout: 900
import fernhill
from ballast import stress

con = fernhill.connect()
inp = stress.inputs(con)
s0 = inp["start"]
h = stress.default_history(con)
then = h.set_index(["product", "year"]).rate
replays = {"2020 again": ("2020-01-31", 24, 2020, 2026),
           "rates again": ("2022-01-31", 36, 2023, 2027)}
out = {}
for name, (first, months, year, at) in replays.items():
    p = stress.historical(con, first, months)
    r = stress.project(inp, p, name)
    out[name] = r
    print(f"{name}: the months from {first[:7]} replayed from today")
    print(f"{'':<6}{'unemp':>7}{'rate':>7}{'houses':>8}{'loss $m':>9}"
          f"{'provision':>10}{'CET1 SA':>9}")
    prev = s0["hpi"]
    for y in r["years"].itertuples():
        print(f"{y.year:<6}{y.u:>7.2f}{y.policy:>7.2f}"
              f"{y.hpi / prev - 1:>+8.1%}{y.loss / 1e8:>9.1f}"
              f"{y.provision / 1e8:>10.1f}{y.cet1_sa:>9.1%}")
        prev = y.hpi
    pr = r["products"].set_index(["product", "year"])
    print(f"  default rate in {at} on today's book, against {year}'s:")
    for prod, lab in (("personal", "personal"), ("card", "card"),
                      ("sme_term", "SME term")):
        print(f"    {lab:<10}{pr.loc[(prod, at), 'rate']:>7.2%}"
              f"  ({then[(prod, year)]:.2%} in {year})")
    c = r["products"]
    c = c[c["product"].str.startswith("commercial") & (c.year == at)]
    rate = c.defaults.sum() / len(inp["cb"])
    print(f"    {'commercial':<10}{rate:>7.2%}  "
          f"({then[('commercial', year)]:.2%} of clients in {year})")
    print()
for name, r in out.items():
    print(f"{name}: trough {r['trough_sa']:.1%} standardised, "
          f"three-year loss ${r['years'].loss.sum() / 1e8:,.0f}m")
