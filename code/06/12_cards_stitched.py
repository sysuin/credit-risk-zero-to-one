# The same card vintages with each migrated card followed back to the
# account it replaced, and the defaults the migration counted twice.
import json

import fernhill
from ballast import performance as perf
from ballast.config import ROOT

AGES = (6, 12, 24, 36, 48)
con = fernhill.connect()
print(perf.stitched_history(con, "CK0000001").iloc[73:77]
      .to_string(index=False))
links, chains = con.execute("""
    SELECT count(*), count(*) FILTER (WHERE root_id <> account_id
                                        AND account_id LIKE 'CK%')
    FROM account_root WHERE root_id <> account_id""").fetchone()
print(f"accounts with a predecessor: {links:,} (all CK: "
      f"{links == chains})\n")

naive = perf.default_episodes(con, "dod2021", stitched=False)
eps = perf.default_episodes(con, "dod2021", stitched=True)
table = perf.vintage_table(con, "card", eps, stitched=True)
print(f"{'opened':<8}{'cards':>7}" + "".join(
    f"{'m' + str(k):>7}" for k in AGES))
for cohort, row in table.iterrows():
    cells = "".join(f"{row[k]:>7.1%}" if row[k] == row[k]
                    else f"{'.':>7}" for k in AGES)
    print(f"{cohort:<8}{int(row['accounts']):>7,}{cells}")

twice = naive[naive["account_id"].str.startswith("CK")
              & (naive["default_month"].astype(str) == "2022-03-31")]
recorded = con.execute("""
    SELECT count(*) FROM defaults
    WHERE account_id LIKE 'CK%' AND default_month = '2022-03-31'
""").fetchone()[0]
print(f"\ndefault episodes: {len(naive):,} by account id, "
      f"{len(eps):,} stitched")
open_at_move = set(con.execute("""
    SELECT a.account_id FROM accounts a
    JOIN accounts o ON o.account_id = a.predecessor_id
    WHERE o.account_id IN (SELECT unnest(?))""", [list(
        naive.loc[naive["cure_month"].isna(), "account_id"])]
                                ).fetchnumpy()["account_id"])
print(f"CK cards in default in March 2022: {len(twice)}, of which "
      f"{twice['account_id'].isin(open_at_move).sum()}\n  were already "
      f"in default under their old number")
print(f"the same cards in Fernhill's defaults table: {recorded}")

old = perf.vintage_table(con, "card", naive, stitched=False)
json.dump({kind: {c: [None if v != v else v for v in t.loc[c, 0:60]]
                  for c in ("2019", "2021")}
           for kind, t in (("naive", old), ("stitched", table))},
          open(ROOT / "code/06/12_cards_stitched.json", "w"))
