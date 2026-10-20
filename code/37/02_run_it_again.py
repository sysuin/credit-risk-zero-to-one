# Generate the loan book a second time, apart, and compare checksums.
# timeout: 1200
import contextlib
import io
import shutil

import duckdb

import fernhill.generate as gen
from ballast.config import LOANBOOK, SANDBOX, SEED, TRUTH

AGAIN = SANDBOX / "ch37" / "again"
AGAIN.mkdir(parents=True, exist_ok=True)
gen.FERNHILL = AGAIN                       # the same program, writing
gen.LOANBOOK = AGAIN / "loanbook.duckdb"   # somewhere else
gen.TRUTH = AGAIN / "truth.duckdb"
with contextlib.redirect_stdout(io.StringIO()):
    gen.main()


def checksums(path):
    con = duckdb.connect(str(path), read_only=True,
                         config={"threads": 1})
    names = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables "
        "ORDER BY 1").fetchall()]
    out = {}
    for name in names:
        out[name] = con.execute(
            f"SELECT count(*), sum(hash(t)) FROM {name} t").fetchone()
    con.close()
    return out


print(f"seed {SEED}; last 12 digits of each table's checksum")
print(f"{'table':<14}{'rows':>11}{'published':>15}{'run again':>15}")
same = total = 0
for book, again in ((LOANBOOK, gen.LOANBOOK), (TRUTH, gen.TRUTH)):
    a, b = checksums(book), checksums(again)
    total += len(a)
    same += sum(a[k] == b.get(k) for k in a)
    for name in ("applications", "performance", "recoveries",
                 "pd12", "corporate_pd"):
        if name in a:
            n, h = a[name]
            print(f"{name:<14}{n:>11,}{str(h)[-12:]:>15}"
                  f"{str(b[name][1])[-12:]:>15}")
print(f"tables identical, both databases: {same} of {total}")
shutil.rmtree(AGAIN)
