"""Loss given default, measured from Fernhill's workouts.

A default starts a **workout**: everything that happens until the
debt is repaid, cured, or written off and collected. This module
turns Fernhill's records into one row per workout and one row per
cash flow, and measures loss given default the way a lender's
modelling team does:

- every default episode (Chapter 6's, stitched across the card
  migration) is a workout, whatever it ended in;
- the cash it produced is the borrower's own payments while in
  default, everything in `recoveries` (collections, debt sales,
  collateral sales, guarantees) and, with a minus sign, the costs;
  a cure hands back a performing loan, counted as its balance;
- each cash flow is discounted back to the month of default;
- LGD = 1 - discounted net cash / exposure at default, floored at
  zero (a recovery cannot be worth more than what was owed); a cure
  counts as a loss of zero.

Workouts still running on 31 December 2025 are censored: their cash
so far understates what they will bring. `recovery_triangle` and
`complete` estimate what is still to come from the mature workouts.

    import fernhill
    from ballast.parameters import lgd
    con = fernhill.connect()
    w = lgd.workouts(con)
    f = lgd.cash_flows(con, w)
    w = lgd.realised(w, f, lgd.discount_rates(con, w))
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ballast import performance as perf
from ballast.config import AS_OF, BALLAST

DISCOUNT_PREMIUM_PCT = 5.0     # over the cost of funds at default
OUTCOMES = ("cured", "paid_off", "written_off", "open")
RECOVERY_KINDS = ("payment", "cure", "collections_payment",
                  "debt_sale", "collateral_sale", "guarantee", "cost")
MAX_MONTHS = 72                # a workout's recoveries, followed this far
MIN_WORKOUTS = 30              # for a year to count towards downturn
PARAMS = BALLAST / "parameters" / "lgd.json"


# ------------------------------------------------------------ workouts

def workouts(con, definition: str = "dod2021") -> pd.DataFrame:
    """One row per default episode, with how and when it ended.

    `outcome` is `cured` (back to paying, after probation),
    `paid_off` (repaid while in default), `written_off` (charged
    off, car repossessed, home or business security sold) or `open`
    (still in default on AS_OF). `end_month` is the cure or closing
    month, NaT when open.
    """
    eps = perf.default_episodes(con, definition)       # stitched
    eps = eps.sort_values(["account_id", "default_month"])
    eps = eps.reset_index(drop=True)
    eps["default_month"] = pd.to_datetime(eps["default_month"])
    eps["next_default"] = (eps.groupby("account_id")["default_month"]
                           .shift(-1))
    chain = con.execute("""
        SELECT r.root_id AS account_id,
               any_value(a.open_date) FILTER (
                   WHERE a.account_id = r.root_id) AS open_date,
               any_value(a.amount_cents) FILTER (
                   WHERE a.account_id = r.root_id) AS amount_cents,
               any_value(a.collateral_value_cents) FILTER (
                   WHERE a.account_id = r.root_id) AS collateral_cents,
               max(a.close_date) FILTER (
                   WHERE a.close_reason <> 'migrated') AS close_date,
               any_value(a.close_reason) FILTER (
                   WHERE a.close_reason <> 'migrated') AS close_reason
        FROM account_root r JOIN accounts a USING (account_id)
        GROUP BY 1""").df()
    w = eps.merge(chain, on="account_id", how="left")
    rate = con.execute("""
        SELECT root_id AS account_id, month AS default_month,
               any_value(rate_pct) AS rate_pct
        FROM history WHERE missed >= 3 OR bankrupt
           OR status = 'charged_off'
        GROUP BY 1, 2""").df()
    rate["default_month"] = pd.to_datetime(rate["default_month"])
    w = w.merge(rate, on=["account_id", "default_month"], how="left")
    closed = w["close_date"].notna() & (
        w["next_default"].isna()
        | (pd.to_datetime(w["close_date"])
           < pd.to_datetime(w["next_default"])))
    lost = w["close_reason"].isin(perf.WRITTEN_OFF)
    w["outcome"] = np.select(
        [w["cure_month"].notna(), closed & lost, closed],
        ["cured", "written_off", "paid_off"], "open")
    w["end_month"] = pd.to_datetime(
        np.where(w["outcome"] == "cured", w["cure_month"],
                 np.where(w["outcome"] == "open", pd.NaT,
                          w["close_date"])))
    w["end_month"] = w["end_month"] + pd.offsets.MonthEnd(0)
    w.insert(0, "workout", np.arange(len(w)))
    w.attrs.update(definition=definition)
    return w


def cash_flows(con, w: pd.DataFrame) -> pd.DataFrame:
    """Every cash flow of every workout, by month and kind, in cents.

    `payment` is what the borrower paid after the default month, up
    to the cure or closure (or AS_OF); `cure` is the balance handed
    back as a performing loan at the cure; the rest are the rows of
    `recoveries` on any account in the chain, which all belong to its
    written-off workout (the last). `months` counts from the default
    month; a recovery dated before it (a guarantee paid on an earlier
    default of the same loan) counts as month 0.
    """
    cols = ["workout", "account_id", "default_month", "end_month",
            "next_default", "outcome"]
    con.register("_w", w[cols])
    f = con.execute(f"""
        SELECT w.workout, h.month, 'payment' AS kind,
               h.paid_cents AS amount_cents
        FROM _w w JOIN history h ON h.root_id = w.account_id
         AND h.month > w.default_month
         AND h.month <= coalesce(w.end_month, DATE '{AS_OF}')
        WHERE h.paid_cents <> 0
        UNION ALL
        SELECT w.workout, h.month, 'cure', h.balance_cents
        FROM _w w JOIN history h ON h.root_id = w.account_id
         AND h.month = w.end_month
        WHERE w.outcome = 'cured'
        UNION ALL
        SELECT w.workout, r.month, r.kind, r.amount_cents
        FROM _w w JOIN account_root a ON a.root_id = w.account_id
        JOIN recoveries r ON r.account_id = a.account_id
        WHERE w.outcome = 'written_off'
        ORDER BY 1, 2, 3""").df()
    con.unregister("_w")
    start = w.set_index("workout")["default_month"]
    d0 = pd.to_datetime(f["workout"].map(start))
    m = pd.to_datetime(f["month"])
    f["months"] = ((m.dt.year - d0.dt.year) * 12
                   + m.dt.month - d0.dt.month).clip(lower=0)
    return f


def as_at(w: pd.DataFrame, as_of) -> pd.DataFrame:
    """The workouts as they stood on an earlier date: only defaults
    by then, and any that ended later shown as still open."""
    when = pd.Timestamp(as_of)
    out = w[w["default_month"] <= when].copy()
    later = out["end_month"] > when
    out.loc[later, "outcome"] = "open"
    out.loc[later, "end_month"] = pd.NaT
    return out


# --------------------------------------------------------- discounting

def discount_rates(con, w: pd.DataFrame, basis: str = "funding",
                   premium_pct: float = DISCOUNT_PREMIUM_PCT
                   ) -> pd.Series:
    """Each workout's annual discount rate, in per cent.

    `funding`: Fernhill's cost of funds in the month of default plus
    a premium for the risk that the recoveries do not arrive.
    `contract`: the loan's own rate at default (IFRS 9 discounts at
    the effective interest rate). `none`: zero.
    """
    if basis == "none":
        return pd.Series(0.0, index=w["workout"])
    if basis == "contract":
        return pd.Series(w["rate_pct"].fillna(0.0).to_numpy(),
                         index=w["workout"])
    if basis != "funding":
        raise ValueError(f"unknown basis {basis!r}")
    cof = con.execute("SELECT month, cost_of_funds_pct "
                      "FROM market_rates").df()
    cof = cof.set_index(pd.to_datetime(cof["month"]))
    cof = cof["cost_of_funds_pct"]
    return pd.Series(w["default_month"].map(cof).to_numpy()
                     + premium_pct, index=w["workout"])


def discounted(f: pd.DataFrame, rates: pd.Series) -> pd.Series:
    """Each cash flow's value in the month of default, in cents."""
    r = f["workout"].map(rates).to_numpy() / 1200
    return f["amount_cents"] / (1 + r) ** f["months"].to_numpy()


# ------------------------------------------------------------ realised

def realised(w: pd.DataFrame, f: pd.DataFrame,
             rates: pd.Series | None = None) -> pd.DataFrame:
    """Add each workout's cash, its present value and its LGD.

    `net_cents` is undiscounted net cash; `pv_cents` its value at
    default; `lgd_raw` = 1 - pv / EAD; `lgd` floors that at zero,
    and is zero for a cure (the loan is back, owed in full).
    Open workouts get the LGD of their cash so far, which is
    censored: read `outcome` before averaging.
    """
    if rates is None:
        rates = pd.Series(0.0, index=w["workout"])
    pv = discounted(f, rates).groupby(f["workout"]).sum()
    net = f.groupby("workout")["amount_cents"].sum()
    out = w.copy()
    out["net_cents"] = out["workout"].map(net).fillna(0.0)
    out["pv_cents"] = out["workout"].map(pv).fillna(0.0)
    ead = out["ead_cents"].where(out["ead_cents"] > 0)
    out["lgd_raw"] = 1 - out["pv_cents"] / ead      # NaN if no EAD
    out["lgd"] = out["lgd_raw"].clip(lower=0.0)
    out.loc[out["outcome"].eq("cured") & ead.notna(), "lgd"] = 0.0
    return out


def pooled(w: pd.DataFrame, by="product", col: str = "lgd"
           ) -> pd.DataFrame:
    """LGD weighted by exposure (sum of losses over sum of EAD) and
    the plain average of workouts' LGDs, with counts."""
    w = w[w[col].notna()]
    g = w.assign(_loss=w[col] * w["ead_cents"]).groupby(by)
    return pd.DataFrame({
        "workouts": g.size(),
        "ead_cents": g["ead_cents"].sum(),
        "lgd": g["_loss"].sum() / g["ead_cents"].sum(),
        "mean_lgd": g[col].mean(),
    })


# ----------------------------------------------------------- censoring

def months_observed(w: pd.DataFrame, as_of=AS_OF) -> pd.Series:
    """Months from each default to `as_of`: how long it has been
    watched."""
    last = pd.Timestamp(as_of)
    d = w["default_month"]
    return (last.year - d.dt.year) * 12 + last.month - d.dt.month


def recovery_triangle(w: pd.DataFrame, f: pd.DataFrame,
                      rates: pd.Series, cohort: str = "year",
                      max_months: int = MAX_MONTHS,
                      as_of=AS_OF) -> pd.DataFrame:
    """Cumulative discounted recovery as a share of EAD, by default
    cohort (rows) and months since default (columns).

    Each workout's cumulative recovery is capped at its EAD (the
    floor on LGD, applied month by month), and a cure counts as
    recovering all of it from the month the cure is confirmed. A cell is NaN once any
    workout in the cohort has not been watched that long at
    `as_of`; cash after `as_of` is ignored. `attrs["ead"]` holds
    each cohort's exposure.
    """
    w = w[(w["default_month"] <= pd.Timestamp(as_of))
          & (w["ead_cents"] > 0)]
    f = f[f["workout"].isin(w["workout"])
          & (pd.to_datetime(f["month"]) <= pd.Timestamp(as_of))]
    v = f.assign(pv=discounted(f, rates))
    v["months"] = v["months"].clip(upper=max_months)
    by_m = v.groupby(["workout", "months"])["pv"].sum().unstack(
        fill_value=0.0)
    by_m = by_m.reindex(index=w["workout"],
                        columns=range(max_months + 1), fill_value=0.0)
    ead = w.set_index("workout")["ead_cents"].astype(float)
    cum = by_m.cumsum(axis=1).clip(upper=ead, axis=0)
    # A cure is a full recovery from the month it is confirmed.
    cured = w[(w["outcome"] == "cured")
              & (w["end_month"] <= pd.Timestamp(as_of))]
    at = ((cured["end_month"].dt.year - cured["default_month"].dt.year)
          * 12 + cured["end_month"].dt.month
          - cured["default_month"].dt.month).clip(upper=max_months)
    for wid, k in zip(cured["workout"], at):
        cum.loc[wid, k:] = ead.loc[wid]
    freq = {"year": "Y", "quarter": "Q"}[cohort]
    key = w.set_index("workout")["default_month"].dt.to_period(freq)
    seen = months_observed(w, as_of).set_axis(w["workout"])
    rows, size = {}, {}
    for c, ids in key.groupby(key).groups.items():
        share = cum.loc[ids].sum() / ead.loc[ids].sum()
        mask = np.arange(max_months + 1) <= seen.loc[ids].min()
        rows[str(c)] = np.where(mask, share.to_numpy(), np.nan)
        size[str(c)] = ead.loc[ids].sum()
    out = pd.DataFrame.from_dict(rows, orient="index",
                                 columns=range(max_months + 1))
    out.index.name = "cohort"
    out.attrs["ead"] = pd.Series(size)
    return out


def development_factors(tri: pd.DataFrame) -> pd.Series:
    """Chain-ladder factors: for each month k, the cohorts' recovery
    at k + 1 over their recovery at k, among cohorts seen at both,
    weighted by exposure (the usual volume-weighted form)."""
    ead = tri.attrs.get("ead", pd.Series(1.0, index=tri.index))
    out = {}
    cols = list(tri.columns)
    for k, k1 in zip(cols, cols[1:]):
        both = tri[[k, k1]].dropna()
        e = ead.loc[both.index]
        base = (both[k] * e).sum()
        out[k] = (both[k1] * e).sum() / base if base > 0 else 1.0
    return pd.Series(out)


def increments(tri: pd.DataFrame) -> pd.Series:
    """Recovery added in month k + 1, per dollar of EAD, averaged over
    the cohorts seen at k + 1 (weighted by exposure)."""
    ead = tri.attrs.get("ead", pd.Series(1.0, index=tri.index))
    out = {}
    cols = list(tri.columns)
    for k, k1 in zip(cols, cols[1:]):
        both = tri[[k, k1]].dropna()
        e = ead.loc[both.index]
        out[k] = (((both[k1] - both[k]) * e).sum() / e.sum()
                  if len(both) else 0.0)
    return pd.Series(out)


def complete(tri: pd.DataFrame, method: str = "chain") -> pd.Series:
    """Each cohort's eventual recovery share of EAD.

    `chain` multiplies the last observed cell by the development
    factors still to come; `additive` adds the recovery per dollar
    that mature cohorts went on to collect after that age, which
    still works for a cohort that has recovered nothing yet.
    """
    last_col = tri.columns[-1]
    if method == "chain":
        steps = development_factors(tri)
    elif method == "additive":
        steps = increments(tri)
    else:
        raise ValueError(f"unknown method {method!r}")
    out = {}
    for c, row in tri.iterrows():
        seen = row.dropna()
        k, got = seen.index[-1], seen.iloc[-1]
        rest = steps.loc[k:last_col - 1]
        final = got * rest.prod() if method == "chain" else got + rest.sum()
        out[c] = float(np.clip(final, 0.0, 1.0))
    return pd.Series(out, name="recovery")


def completed_lgd(tri: pd.DataFrame, method: str = "chain",
                  by: str = "year") -> pd.Series:
    """Eventual LGD by default year (or cohort), from `complete`,
    with cohorts pooled by exposure."""
    rec = complete(tri, method)
    ead = tri.attrs["ead"].loc[rec.index]
    key = [c[:4] for c in rec.index] if by == "year" else rec.index
    loss = ((1 - rec) * ead).groupby(key).sum()
    return loss / ead.groupby(key).sum()


def estimate(w: pd.DataFrame, f: pd.DataFrame, rates: pd.Series,
             min_workouts: int = MIN_WORKOUTS,
             last_year: int = AS_OF.year - 2) -> dict:
    """Ballast's LGD for one product's workouts.

    `lgd`: every cohort, its unfinished workouts completed by the
    additive recovery curve, pooled by EAD. `by_year`: the same, year
    by year. `downturn`: the worst year up to `last_year` (by default
    the last with two years of recoveries) with at least
    `min_workouts` workouts, and never below `lgd`.
    """
    tq = recovery_triangle(w, f, rates, cohort="quarter")
    rec = complete(tq, "additive")
    ead = tq.attrs["ead"].loc[rec.index]
    by_year = completed_lgd(tq, "additive")
    years = w["default_month"].dt.year.astype(str).value_counts()
    ok = [y for y in by_year.index
          if years.get(y, 0) >= min_workouts and int(y) <= last_year]
    worst = max((by_year[y] for y in ok), default=np.nan)
    long_run = float(1 - (rec * ead).sum() / ead.sum())
    return {"lgd": long_run,
            "downturn": float(np.nanmax([worst, long_run])),
            "worst_year": (max(ok, key=lambda y: by_year[y])
                           if ok else None),
            "by_year": {y: float(v) for y, v in by_year.items()},
            "workouts": int(len(w)),
            "cure_rate": float((w["outcome"] == "cured").mean())}


# ------------------------------------------------------- the estimate

def save(estimates: dict, path=PARAMS) -> None:
    """Write the LGD estimates Ballast's later modules read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(estimates, indent=1, sort_keys=True))


def load(path=PARAMS) -> dict:
    """The LGD estimates saved by `save`."""
    return json.loads(path.read_text())
