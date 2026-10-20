# One validation report as Ballast writes it: Fernhill's own rating
# model, the one the validation could not approve.
from ballast import validation as vd

print("\n".join(vd.render(vd.REPORTS["FRM"])))
