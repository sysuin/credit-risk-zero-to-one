"""Fernhill's loan book, measured: Ballast v0.2.

Every later model inherits its definitions from here:

- default flags under both of Fernhill's definitions: `dpd90`, the
  plain 90 days past due it used until 2020, and `dod2021`, the
  definition it adopted in January 2021;
- account histories stitched across the March 2022 card migration,
  so a card that changed its number is one account, not two;
- vintage tables: the share of each cohort that has defaulted by
  each month on book, blank where the cohort is too young to say;
- roll-rate matrices: where accounts in each arrears bucket are one
  month end later;
- a year's portfolio rates, each with its denominator named.

    import fernhill
    from ballast import performance as perf
    con = fernhill.connect()
    eps = perf.default_episodes(con, "dod2021")
    table = perf.vintage_table(con, "personal", eps)

Everything is computed in SQL on the connection, which may be
read-only: the module adds two temporary tables to it and nothing
else.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from ballast.config import AS_OF

DEFINITIONS = ("dpd90", "dod2021")
DOD2021_FROM = dt.date(2021, 1, 31)   # the first month end it applied
MATERIAL_CENTS = 10_000               # arrears must exceed $100 ...
MATERIAL_SHARE = 0.01                 # ... and 1% of the balance
PROBATION = {"dpd90": 1, "dod2021": 3}  # clean months to cure

OPEN = ("up_to_date", "arrears", "default")
PAID_OFF = ("repaid", "prepaid", "closed_by_customer")
WRITTEN_OFF = ("charged_off", "vehicle_repossessed", "property_sold",
               "collateral_sold")
BUCKETS = ["current", "30", "60", "90", "120", "150", "180+"]
EXITS = ["paid off", "written off"]
EPISODE_COLUMNS = ["account_id", "product", "default_month", "trigger",
                   "ead_cents", "cure_month"]


# ------------------------------------------------------ the definitions

def material(arrears_cents: int, balance_cents: int) -> bool:
    """Arrears big enough to count: over $100 and over 1% of balance."""
    return (arrears_cents > MATERIAL_CENTS
            and arrears_cents > MATERIAL_SHARE * balance_cents)


def trigger(definition: str, missed: int, arrears_cents: int,
            balance_cents: int, charged_off: bool,
            bankrupt: bool) -> str | None:
    """Why this month end is a default under a definition, or None."""
    if definition == "dpd90":
        return "days_past_due" if missed >= 3 else None
    if definition != "dod2021":
        raise ValueError(f"unknown definition {definition!r}")
    if missed >= 3 and material(arrears_cents, balance_cents):
        return "days_past_due"
    if bankrupt:
        return "bankruptcy"
    if charged_off:
        return "charged_off"
    return None


def flag_defaults(rows, definition: str) -> list[list]:
    """Default episodes from month-end rows sorted by account, month.

    Each row is (account_id, product, month, missed, arrears_cents,
    balance_cents, charged_off, bankrupt). An episode starts at the
    first month end that triggers while the account is not in
    default, and ends (cures) after PROBATION[definition] months in a
    row with nothing missed and nothing triggering.
    """
    need = PROBATION[definition]
    out, key, in_default, clean = [], None, False, 0
    for k, product, month, missed, arrears, balance, co, bk in rows:
        if k != key:
            key, in_default, clean = k, False, 0
        why = trigger(definition, missed, arrears, balance, co, bk)
        if not in_default:
            if why:
                out.append([k, product, month, why, balance, None])
                in_default, clean = True, 0
        else:
            clean = clean + 1 if (missed == 0 and not why) else 0
            if clean >= need:
                out[-1][5] = month
                in_default = False
    return out


# ------------------------------------------------- stitching histories

def prepare(con) -> None:
    """Add `account_root` and `history` to the connection, once.

    `account_root` maps every account to the first account in its
    chain of predecessors (a card migrated in March 2022 maps to the
    card it replaced) and gives that root's opening date. `history`
    is every performance row with both ids, both opening dates and
    the account's first month with a payment due.
    """
    have = con.execute("SELECT count(*) FROM duckdb_tables() "
                       "WHERE table_name = 'history'").fetchone()[0]
    if have:
        return
    con.execute("""
        CREATE TEMP TABLE account_root AS
        WITH RECURSIVE chain(account_id, root_id) AS (
            SELECT account_id, account_id FROM accounts
            WHERE predecessor_id IS NULL
            UNION ALL
            SELECT a.account_id, c.root_id
            FROM accounts a JOIN chain c
              ON a.predecessor_id = c.account_id
        )
        SELECT c.account_id, c.root_id, a.product,
               a.open_date, r.open_date AS root_open,
               a.amount_cents
        FROM chain c
        JOIN accounts a ON a.account_id = c.account_id
        JOIN accounts r ON r.account_id = c.root_id
    """)
    con.execute("""
        CREATE TEMP TABLE history AS
        SELECT p.*, r.root_id, r.open_date, r.root_open,
               min(p.month) FILTER (WHERE p.scheduled_cents > 0)
                   OVER (PARTITION BY r.root_id) AS first_due,
               b.account_id IS NOT NULL AS bankrupt
        FROM performance p
        JOIN account_root r USING (account_id)
        LEFT JOIN (SELECT DISTINCT account_id, event_date
                   FROM account_events WHERE event = 'bankruptcy') b
          ON b.account_id = p.account_id AND b.event_date = p.month
    """)


def _key(stitched: bool) -> str:
    return "root_id" if stitched else "account_id"


def stitched_history(con, account_id: str) -> pd.DataFrame:
    """One account's whole life, under every number it has had."""
    prepare(con)
    return con.execute("""
        SELECT account_id, month, balance_cents, missed, status
        FROM history
        WHERE root_id = (SELECT root_id FROM account_root
                         WHERE account_id = ?)
        ORDER BY month""", [account_id]).df()


# ------------------------------------------------------------ defaults

def default_episodes(con, definition: str = "dod2021",
                     stitched: bool = True,
                     products=None) -> pd.DataFrame:
    """Every default episode under one definition, from the rows.

    With `stitched`, a migrated card's rows continue its
    predecessor's, and episodes carry the predecessor's id.
    """
    prepare(con)
    key = _key(stitched)
    where = ""
    if products is not None:
        names = ", ".join(f"'{p}'" for p in products)
        where = f"AND product IN ({names})"
    rows = con.execute(f"""
        SELECT {key}, product, month, missed, arrears_cents,
               balance_cents, status = 'charged_off', bankrupt
        FROM history
        WHERE {key} IN (SELECT {key} FROM history
                        WHERE missed >= 3 OR bankrupt
                           OR status = 'charged_off') {where}
        ORDER BY {key}, month""").fetchall()
    out = pd.DataFrame(flag_defaults(rows, definition),
                       columns=EPISODE_COLUMNS)
    out.attrs.update(definition=definition, stitched=stitched)
    return out


def first_defaults(episodes: pd.DataFrame) -> pd.DataFrame:
    """Each account's first default only."""
    return (episodes.sort_values(["account_id", "default_month"])
            .drop_duplicates("account_id").reset_index(drop=True))


# ------------------------------------------------------------ vintages

def _months(a: pd.Series, b: pd.Series) -> np.ndarray:
    """Whole calendar months from date a to date b."""
    a, b = pd.to_datetime(a), pd.to_datetime(b)
    return ((b.dt.year - a.dt.year) * 12
            + (b.dt.month - a.dt.month)).to_numpy()


def cohort_accounts(con, product: str, episodes: pd.DataFrame,
                    stitched: bool = True,
                    clock: str = "open") -> pd.DataFrame:
    """One row per account: its cohort start and when it defaulted.

    `clock="open"` counts months on book from the opening month;
    `clock="due"` counts from the month before the first payment
    was due, which differs only for loans with a payment-free start
    (Fernhill's emergency loans: first payment in month 13).
    `start` is the month the clock starts; `default_mob` is the
    clock's reading at the first default (NaN if none).
    """
    prepare(con)
    if episodes.attrs.get("stitched", stitched) != stitched:
        raise ValueError("episodes and vintages must agree on "
                         "stitching")
    key = _key(stitched)
    opened = "root_open" if stitched else "open_date"
    acc = con.execute(f"""
        SELECT {key} AS account_id, any_value({opened}) AS open_date,
               any_value(first_due) AS first_due
        FROM history WHERE product = ?
        GROUP BY 1 ORDER BY 1""", [product]).df()
    acc["open_month"] = (pd.to_datetime(acc["open_date"])
                         + pd.offsets.MonthEnd(0))
    if clock == "open":
        acc["start"] = acc["open_month"]
    elif clock == "due":
        acc["start"] = (pd.to_datetime(acc["first_due"])
                        - pd.offsets.MonthEnd(1))
        acc["start"] = acc["start"].fillna(acc["open_month"])
    else:
        raise ValueError(f"unknown clock {clock!r}")
    first = first_defaults(episodes)[["account_id", "default_month"]]
    acc = acc.merge(first, on="account_id", how="left")
    mob = _months(acc["start"], acc["default_month"])
    acc["default_mob"] = np.where(acc["default_month"].isna(),
                                  np.nan, mob)
    return acc


def vintage_table(con, product: str, episodes: pd.DataFrame,
                  cohort: str = "year", max_mob: int = 60,
                  stitched: bool = True,
                  clock: str = "open") -> pd.DataFrame:
    """Cumulative share of each cohort defaulted, by months on book.

    Rows are cohorts (the year or quarter the accounts opened),
    columns are months on the clock, 0..max_mob. A cell is NaN when
    any account in the cohort has not yet reached that age at
    AS_OF: a young cohort's curve stops instead of looking flat.
    """
    acc = cohort_accounts(con, product, episodes, stitched, clock)
    freq = {"year": "Y", "quarter": "Q"}[cohort]
    acc["cohort"] = acc["open_month"].dt.to_period(freq)
    last = pd.Timestamp(AS_OF)
    acc["seen"] = ((last.year - acc["start"].dt.year) * 12
                   + last.month - acc["start"].dt.month)
    mobs = np.arange(max_mob + 1)
    table, size = {}, {}
    for c, g in acc.groupby("cohort", sort=True):
        hit = g["default_mob"].to_numpy()
        share = [(hit <= k).sum() / len(g) for k in mobs]
        table[str(c)] = np.where(mobs <= g["seen"].min(), share,
                                 np.nan)
        size[str(c)] = len(g)
    out = pd.DataFrame.from_dict(table, orient="index", columns=mobs)
    out.index.name = "cohort"
    out.insert(0, "accounts", pd.Series(size))
    return out


# ---------------------------------------------------------- roll rates

def _bucket(missed: str, status: str) -> str:
    return f"""CASE
        WHEN {status} IN {WRITTEN_OFF} THEN 'written off'
        WHEN {status} IN {PAID_OFF} THEN 'paid off'
        WHEN {missed} >= 6 THEN '180+'
        WHEN {missed} = 0 THEN 'current'
        ELSE CAST({missed} * 30 AS VARCHAR) END"""


def transition_matrix(con, product: str, start: dt.date,
                      end: dt.date, stitched: bool = True,
                      weight: str = "count") -> pd.DataFrame:
    """Where accounts in each bucket are one month end later.

    Counts (or balances, `weight="balance"`) moving from each open
    bucket at month t, for t from start to end, to each bucket or
    exit at t + 1, as row shares. `n` is the row's total.
    """
    prepare(con)
    key = _key(stitched)
    w = "1" if weight == "count" else "balance_cents"
    df = con.execute(f"""
        WITH h AS (
            SELECT month, status, {w} AS w,
                   {_bucket('missed', 'status')} AS frm,
                   lead({_bucket('missed', 'status')}) OVER (
                       PARTITION BY {key} ORDER BY month) AS too,
                   lead(month) OVER (
                       PARTITION BY {key} ORDER BY month) AS nxt
            FROM history WHERE product = ?
        )
        SELECT frm, too, sum(w) AS n FROM h
        WHERE month BETWEEN ? AND ? AND status IN {OPEN}
          AND nxt = last_day(month + INTERVAL 1 MONTH)
        GROUP BY ALL""", [product, start, end]).df()
    m = df.pivot(index="frm", columns="too", values="n").fillna(0)
    rows = [b for b in BUCKETS if b in m.index]
    cols = [b for b in BUCKETS + EXITS if b in m.columns]
    m = m.reindex(index=rows, columns=cols, fill_value=0)
    n = m.sum(axis=1)
    out = m.div(n, axis=0)
    out["n"] = n.astype("int64")
    return out


def project(matrix: pd.DataFrame, months: int) -> pd.DataFrame:
    """Where each bucket's accounts are `months` later, if every
    month moves them as the matrix says. Exits are absorbing."""
    states = [b for b in BUCKETS
              if b in matrix.index or b in matrix.columns] + EXITS
    p = matrix.reindex(index=states, columns=states, fill_value=0.0)
    for s in states:
        if s not in matrix.index:       # an exit, or never left
            p.loc[s] = 0.0
            p.loc[s, s] = 1.0
    step = p.to_numpy(dtype=float)
    out = np.linalg.matrix_power(step, months)
    return pd.DataFrame(out, index=states, columns=states).loc[
        list(matrix.index)]


def flow_to_loss(matrix: pd.DataFrame) -> pd.DataFrame:
    """Each bucket's roll forward one step, and the chain to loss.

    The flow rate from a bucket is the share that moves one bucket
    worse a month later (from the worst open bucket, the share
    written off); the net flow from a bucket is the product of the
    flow rates from there to write-off.
    """
    rows = [b for b in BUCKETS if b in matrix.index]
    rate = {}
    for b, nxt in zip(rows, rows[1:] + ["written off"]):
        rate[b] = matrix.loc[b, nxt] if nxt in matrix.columns else 0.0
    net, run = {}, 1.0
    for b in reversed(rows):
        run *= rate[b]
        net[b] = run
    return pd.DataFrame({"flow": rate, "to_loss": net}).loc[rows]


# ----------------------------------------------------- portfolio rates

def portfolio_rates(con, product: str, year: int,
                    episodes: pd.DataFrame) -> dict:
    """One year's measures for a product, each with its denominator.

    - `default_rate`: of accounts open and not in default on
      1 January, the share with a new default during the year.
    - `charge_off_rate`, `net_loss_rate`: balances written off
      (less, for net, everything recovered in the year) over the
      average month-end balance of open accounts.
    - `dq30_rate`, `dq90_rate`: share of the 31 December balance of
      open accounts 30+ and 90+ days past due.
    Money is in cents.
    """
    prepare(con)
    key = _key(episodes.attrs.get("stitched", True))
    jan1 = dt.date(year - 1, 12, 31)
    dec31 = dt.date(year, 12, 31)
    m = con.execute(f"""
        SELECT
          count(DISTINCT {key}) FILTER (WHERE month = $j
                AND status IN {OPEN}),
          sum(balance_cents) FILTER (WHERE month BETWEEN $s AND $d
                AND status IN {OPEN}) / 12,
          sum(balance_cents) FILTER (WHERE month BETWEEN $s AND $d
                AND status IN {WRITTEN_OFF}),
          sum(balance_cents) FILTER (WHERE month = $d
                AND status IN {OPEN}),
          sum(balance_cents) FILTER (WHERE month = $d
                AND status IN {OPEN} AND missed >= 1),
          sum(balance_cents) FILTER (WHERE month = $d
                AND status IN {OPEN} AND missed >= 3)
        FROM history WHERE product = $p
    """, {"j": jan1, "s": dt.date(year, 1, 31), "d": dec31,
          "p": product}).fetchone()
    start_n, avg_bal, written, end_bal, dq30, dq90 = m
    recovered = con.execute("""
        SELECT coalesce(sum(r.amount_cents), 0)
        FROM recoveries r JOIN accounts a USING (account_id)
        WHERE a.product = ? AND year(r.month) = ?""",
                            [product, year]).fetchone()[0]
    eps = episodes[episodes["product"] == product]
    month = pd.to_datetime(eps["default_month"])
    cure = pd.to_datetime(eps["cure_month"])
    in_default = eps[(month <= pd.Timestamp(jan1))
                     & (cure.isna() | (cure > pd.Timestamp(jan1)))]
    open_jan = set(con.execute(f"""
        SELECT DISTINCT {key} FROM history
        WHERE product = ? AND month = ? AND status IN {OPEN}""",
                               [product, jan1]).fetchnumpy()[key])
    at_risk = open_jan - set(in_default["account_id"])
    new = eps[(month.dt.year == year)
              & eps["account_id"].isin(at_risk)]
    return {
        "open_1jan": start_n, "at_risk": len(at_risk),
        "defaulted": new["account_id"].nunique(),
        "default_rate": new["account_id"].nunique() / len(at_risk),
        "avg_balance": int(avg_bal), "written_off": int(written or 0),
        "recovered": int(recovered),
        "charge_off_rate": (written or 0) / avg_bal,
        "net_loss_rate": ((written or 0) - recovered) / avg_bal,
        "dq30_rate": (dq30 or 0) / end_bal, "dq90_rate": (dq90 or 0) / end_bal,
    }
