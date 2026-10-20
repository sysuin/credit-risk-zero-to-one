# What security and guarantees brought back: how often each paid,
# how much of the exposure, and how long after default.
import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
lost = w[w["outcome"] == "written_off"].set_index("workout")

CASES = [("government guarantee", "sme_emergency", "guarantee", None),
         ("directors, overdraft", "sme_overdraft", "guarantee", None),
         ("directors, term loan", "sme_term", "guarantee", False),
         ("car sold", "auto", "collateral_sale", None),
         ("home sold", "mortgage", "collateral_sale", None),
         ("business assets sold", "sme_term", "collateral_sale", True)]
print(f"{'':<22}{'written':>8}{'paid':>6}{'share':>7}"
      f"{'of EAD':>8}{'months':>8}")
for label, product, kind, secured in CASES:
    g = lost[lost["product"] == product]
    if secured is not None:
        g = g[g["collateral_cents"].notna() == secured]
    pay = f[(f["kind"] == kind) & f["workout"].isin(g.index)]
    by = pay.groupby("workout").agg(amount=("amount_cents", "sum"),
                                    months=("months", "min"))
    share = by["amount"] / g.loc[by.index, "ead_cents"]
    print(f"{label:<22}{len(g):>8}{len(by):>6}"
          f"{len(by) / len(g):>7.0%}{share.median():>8.0%}"
          f"{by['months'].median():>8.0f}")
print("share: of written-off workouts, the share where it paid;")
print("of EAD and months: medians where it paid")

und = lost[(lost["product"] == "sme_term")]
for sec, g in und.groupby(und["collateral_cents"].notna()):
    w_ = lgd.realised(g.reset_index(), f, lgd.discount_rates(
        con, g.reset_index()))
    print(f"sme_term {'secured' if sec else 'unsecured':<10}"
          f" written-off LGD {lgd.pooled(w_)['lgd'].iloc[0]:.1%}"
          f" ({len(g)} workouts)")
