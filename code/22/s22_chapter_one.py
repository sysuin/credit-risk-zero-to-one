# Exercise 22.1: Chapter 1's one-in-a-thousand year at the correlations
# Fernhill's personal loans support, and at the rules' value.
from ballast import portfolio as pf

N_LOANS, PD, LGD, EAD = 1_000, 0.04, 0.80, 12_000
e = pf.load_json("correlations.json")["personal"]
print(f"{'correlation':<22}{'1 in 1,000':>12}{'x EL':>7}")
for label, rho in [("Fernhill's MLE", e["rho"]),
                   ("top of interval", e["hi"]),
                   ("Chapter 1's RHO", 0.10),
                   ("the rules'", e["rules"])]:
    loss = pf.vasicek_quantile(0.999, PD, rho) * N_LOANS * LGD * EAD
    el = PD * N_LOANS * LGD * EAD
    print(f"{label:<16}{rho:>6.3f}{loss:>12,.0f}{loss / el:>7.2f}")
