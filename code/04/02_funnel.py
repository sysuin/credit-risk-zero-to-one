# The funnel: from applications to accounts, by product and channel.
import json

import fernhill
from ballast.config import ROOT

con = fernhill.connect()

FUNNEL = """
    SELECT {key},
           count(*) AS applied,
           count(*) FILTER (WHERE outcome = 'declined') AS declined,
           count(*) FILTER (WHERE decision = 'approve') AS approved,
           count(*) FILTER (WHERE outcome = 'not_taken_up') AS walked,
           count(*) FILTER (WHERE outcome = 'offer_open') AS open,
           count(*) FILTER (WHERE outcome = 'booked') AS booked
    FROM applications GROUP BY ALL ORDER BY applied DESC
"""


def show(key, rows):
    if key:
        print(f"{key:<10}{'applied':>8}{'declined':>9}{'approved':>9}"
              f"{'walked':>7}{'open':>5}{'booked':>7}{'rate':>6}")
    for k, applied, declined, approved, walked, open_, booked in rows:
        print(f"{k:<10}{applied:>8,}{declined:>9,}{approved:>9,}"
              f"{walked:>7,}{open_:>5}{booked:>7,}"
              f"{booked / applied:>6.0%}")


products = con.execute(FUNNEL.format(key="product")).fetchall()
show("product", products)
total = [sum(r[i] for r in products) for i in range(1, 7)]
show("", [("all", *total)])
print()
channels = con.execute(FUNNEL.format(key="channel")).fetchall()
show("channel", channels)

# Of the approved applicants who did not take the offer, how many
# came through each channel, as a share of that channel's approvals.
print()
for k, applied, declined, approved, walked, open_, booked in channels:
    print(f"{k:<8} {walked / approved:.0%} of approvals walked away")

json.dump({"products": products, "channels": channels},
          open(ROOT / "code/04/02_funnel.json", "w"))
