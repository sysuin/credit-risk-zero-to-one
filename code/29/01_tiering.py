# Walk Ballast's models, measure each one's materiality and evidence,
# tier it by Fernhill's rule, and save the inventory.
import fernhill
from ballast import governance as gv

con = fernhill.connect()
inv = gv.build_inventory(con)
gv.save_inventory(inv)
tier = {e["id"]: e["tier"] for e in inv}


def doubt(e):
    if e["judgement"]:
        return "judgement"
    if e["evidence_n"] is None:
        return "not held" if e["evidence"] == "not held" else "-"
    return "thin" if e["evidence_n"] < gv.THIN_EVIDENCE else "-"


print(f"{'id':<6}{'use':<9}{'level':<7}{'$m':>7}{'evidence':>9}"
      f"  {'doubt':<10}{'own':>4}{'tier':>5} via")
for e in inv:
    if e["own_tier"] is None:
        print(f"{e['id']:<6}{e['use']:<9}{'':<7}{'':>7}"
              f"{e['evidence_n']:>9,}  {e['status']}")
        continue
    ev = "-" if e["evidence_n"] is None else f"{e['evidence_n']:,}"
    # the models that raised this one's tier, if any did
    by = []
    if e["tier"] < e["own_tier"]:
        by = [u for u in e["used_by"] if tier[u] == e["tier"]]
    print(f"{e['id']:<6}{e['use']:<9}{e['level']:<7}"
          f"{gv.money(e['materiality_cents']):>7}{ev:>9}  "
          f"{doubt(e):<10}{e['own_tier']:>4}{e['tier']:>5} "
          f"{','.join(by)}".rstrip())
