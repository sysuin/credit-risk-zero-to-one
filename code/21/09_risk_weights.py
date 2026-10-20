# IRB risk weights by exposure class at an LGD of 45%: the
# correlation each class assumes, and what maturity and the 1.06
# scaling factor do to a company's weight.
from ballast import capital

LGD = 0.45
CLASSES = [("mortgage", "mortgage", None), ("qrre", "card", None),
           ("other_retail", "other retail", None),
           ("corporate", "company", None),
           ("corporate", "company $5m", 5.0)]
pds = [0.0005, 0.001, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20]
print("correlation")
print(f"{'PD':<12}" + "".join(f"{p:>7.2%}" for p in pds))
for cls, name, s in CLASSES:
    r = capital.correlation(pds, cls, s if s else float("nan"))
    print(f"{name:<12}" + "".join(f"{x:>7.3f}" for x in r))
print(f"\nrisk weight, LGD {LGD:.0%}, companies at 2.5 years")
print(f"{'PD':<12}" + "".join(f"{p:>7.2%}" for p in pds))
for cls, name, s in CLASSES:
    rw = capital.risk_weight(pds, LGD, cls, 2.5,
                             s if s else float("nan"))
    print(f"{name:<12}" + "".join(f"{x:>7.0%}" for x in rw))
print("\ncompany at PD 1%: maturity and scaling")
for m in (1.0, 2.5, 5.0):
    a = capital.risk_weight(0.01, LGD, "corporate", m)
    b = capital.risk_weight(0.01, LGD, "corporate", m, scaling=1.06)
    print(f"  {m:.1f} years: {a:.1%}; with 1.06, {b:.1%}")
