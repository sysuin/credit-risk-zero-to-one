# The risk weights Ballast uses for the standardised approach: a
# simplified version of the rules (Appendix C has the real tables).
from ballast import capital as cap

print(f"retail (personal, card, car, small business)  "
      f"{cap.RETAIL_RW:.0%}")
print("residential mortgage, by loan-to-value:")
lo = 0.0
for hi, rw in zip(cap.LTV_EDGES + [None], cap.LTV_RW):
    band = f"over {lo:.0%}" if hi is None else \
        f"{lo:.0%} to {hi:.0%}" if lo else f"up to {hi:.0%}"
    print(f"  {band:<14}{rw:>5.0%}")
    lo = hi
print("companies, by agency rating:")
for k in ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]:
    print(f"  {k:<14}{cap.RATING_RW[k]:>5.0%}")
print(f"  {'unrated':<14}{cap.UNRATED_RW:>5.0%}"
      f"   (sales under ${cap.SME_SALES_M:.0f}m: {cap.SME_RW:.0%})")
print(f"defaulted: {cap.DEFAULTED_RW:.0%}; "
      f"{cap.DEFAULTED_COVERED_RW:.0%} if provisions are "
      f"{cap.COVERED:.0%}+ of it;")
print(f"  mortgages {cap.DEFAULTED_MORTGAGE_RW:.0%}; the exposure is "
      "net of its provision")
print("undrawn limits converted at:")
for k, v in cap.SA_CCF.items():
    print(f"  {k:<22}{v:>5.0%}")
share = cap.GUARANTEED["sme_emergency"]
print(f"guaranteed by the government: {share:.0%} of each emergency"
      " loan, at 0%")
