# Exercise 31.3: a fifteenth step for the run, the securitisation pool
# of Chapter 28, checked against what that chapter printed.
import json

from ballast import run
from ballast.config import BALLAST


def securitisation_step(ctx, rerun):
    deal = json.loads((BALLAST / "securitisation" / "deal.json")
                      .read_text())
    src = run.out(28, "01_pool")
    return [run.Check("car loans in the pool", run.n(deal["loans"]),
                      "4,896", src, 28),
            run.Check("pool balance", run.dollars(deal["pool_cents"]),
                      "92,916,018", src, 28)]


steps = run.STEPS + [("transfer", "28", "saved", securitisation_step)]
report = run.run(rerun=False, steps=steps)
print("\n".join(report.table()[-3:]))
print(f"{sum(c.equal for c in report.checks)} of {len(report.checks)} "
      "figures equal")
