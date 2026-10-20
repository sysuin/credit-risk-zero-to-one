"""Exposure at default: how much more a borrower owes by the time
they default than they owe today.

For a loan the answer is close to the balance. For a card, an
overdraft or a revolving facility the borrower can draw the unused
limit, and borrowers heading for default do. The **credit
conversion factor** (CCF) is the share of today's undrawn limit that
will have been drawn by the default:

    EAD = balance + CCF x (limit - balance)

estimated by the fixed-horizon method: for every default, take the
balance and limit twelve months earlier, and see how much of the
headroom was used by the month of default.

    import fernhill
    from ballast.parameters import ead
    con = fernhill.connect()
    s = ead.ccf_sample(con, "card")
    table = ead.fit_ccf(s)
    ead.exposure(balance, limit, table)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ballast import performance as perf
from ballast.config import BALLAST

HORIZON = 12                       # months before default
BANDS = [0.0, 0.3, 0.5, 0.7, 0.9, np.inf]   # utilisation a year out
PARAMS = BALLAST / "parameters" / "ead.json"


def _band(u: pd.Series, bands=BANDS) -> pd.Series:
    labels = [f"{a:.0%}-{b:.0%}" if np.isfinite(b) else f"{a:.0%}+"
              for a, b in zip(bands, bands[1:])]
    return pd.cut(u, bands, right=False, labels=labels)


# ------------------------------------------------- consumer revolving

def utilisation_before(con, products=("card", "sme_overdraft"),
                       months=(24, 18, 12, 9, 6, 3, 2, 1, 0),
                       definition: str = "dod2021") -> pd.DataFrame:
    """Balance over limit in the months before each default.

    `utilisation` is the sum of balances over the sum of limits (what
    the lender has at stake); `behind` the share with a payment
    missed at the time.
    """
    eps = perf.default_episodes(con, definition, products=products)
    con.register("_eps", eps[["account_id", "product",
                              "default_month"]])
    m = ", ".join(str(k) for k in months)
    out = con.execute(f"""
        SELECT e.product,
               datediff('month', h.month, e.default_month) AS before,
               count(*) AS n,
               sum(h.balance_cents) / sum(h.limit_cents) AS utilisation,
               avg((h.missed > 0)::INT) AS behind
        FROM _eps e JOIN history h ON h.root_id = e.account_id
        WHERE h.limit_cents > 0
          AND datediff('month', h.month, e.default_month) IN ({m})
        GROUP BY ALL ORDER BY 1, 2 DESC""").df()
    con.unregister("_eps")
    return out


def performing_utilisation(con, product: str) -> float:
    """Balance over limit across every up-to-date month end."""
    perf.prepare(con)
    return con.execute("""
        SELECT sum(balance_cents) / sum(limit_cents) FROM history
        WHERE product = ? AND status = 'up_to_date'
          AND limit_cents > 0""", [product]).fetchone()[0]


def ccf_sample(con, product: str, horizon: int = HORIZON,
               definition: str = "dod2021") -> pd.DataFrame:
    """One row per default with the balance and limit `horizon`
    months before it (`b0`, `l0`), the limit at default (`l1`) and
    the exposure at default (`ead`), all in cents. Defaults on
    accounts not yet open `horizon` months before are left out."""
    eps = perf.default_episodes(con, definition, products=[product])
    con.register("_eps", eps[["account_id", "default_month",
                              "ead_cents"]])
    s = con.execute(f"""
        SELECT e.account_id, e.default_month, h0.balance_cents AS b0,
               h0.limit_cents AS l0, h1.limit_cents AS l1,
               e.ead_cents AS ead, h0.missed AS missed0
        FROM _eps e
        JOIN history h0 ON h0.root_id = e.account_id
         AND h0.month = last_day(e.default_month
                                 - INTERVAL {int(horizon)} MONTH)
        JOIN history h1 ON h1.root_id = e.account_id
         AND h1.month = e.default_month
        WHERE h0.limit_cents > 0
        ORDER BY 1, 2""").df()
    con.unregister("_eps")
    s["u0"] = s["b0"] / s["l0"]
    s["ccf"] = (s["ead"] - s["b0"]) / (s["l0"] - s["b0"])
    s.loc[s["l0"] <= s["b0"], "ccf"] = np.nan
    return s


def fit_ccf(sample: pd.DataFrame, bands=BANDS) -> pd.DataFrame:
    """CCF by utilisation band a year before default.

    `ccf` is the extra drawn over the headroom, summed across the
    band (so large limits count for more), floored at zero: a
    borrower who paid down is an EAD of the balance, not less.
    `ccf_median` is the median of each default's own CCF, which is
    unstable where the headroom is small; `ead_limit` is EAD over
    the limit a year earlier. A band with no defaults gets the
    highest CCF of the others.
    """
    s = sample.assign(band=_band(sample["u0"], bands))
    g = s.groupby("band", observed=True)
    drawn = g.apply(lambda d: (d["ead"] - d["b0"]).sum(),
                    include_groups=False)
    room = g.apply(lambda d: (d["l0"] - d["b0"]).clip(lower=0).sum(),
                   include_groups=False)
    out = pd.DataFrame({
        "n": g.size(),
        "u0": g["u0"].mean(),
        "ccf_raw": drawn / room,
        "ccf_median": g["ccf"].median(),
        "ead_limit": g["ead"].sum() / g["l0"].sum(),
        "over_limit": g.apply(lambda d: (d["ead"] > d["l0"]).mean(),
                              include_groups=False),
    })
    out["ccf"] = out["ccf_raw"].clip(lower=0.0)
    # A band with no defaults borrows the highest CCF of the others.
    labels = _band(pd.Series(dtype=float), bands).cat.categories
    out = out.reindex(labels)
    out["n"] = out["n"].fillna(0).astype(int)
    out["ccf"] = out["ccf"].fillna(out["ccf"].max())
    return out


def pooled_ccf(sample: pd.DataFrame) -> float:
    """One CCF for a whole sample: extra drawn over headroom, summed."""
    room = (sample["l0"] - sample["b0"]).clip(lower=0).sum()
    return float((sample["ead"] - sample["b0"]).sum() / room)


def exposure(balance, limit, table: pd.DataFrame, bands=BANDS):
    """EAD from today's balance and limit, with the band's CCF.

    Works on numbers or arrays (cents); never less than the balance.
    """
    b = np.asarray(balance, dtype=float)
    lim = np.asarray(limit, dtype=float)
    u = np.where(lim > 0, b / np.where(lim > 0, lim, 1), np.inf)
    idx = np.clip(np.searchsorted(bands, u, side="right") - 1, 0,
                  len(bands) - 2)
    ccf = table["ccf"].to_numpy()[idx]
    return np.maximum(b, b + ccf * np.maximum(lim - b, 0))


# ------------------------------------------------- commercial revolvers

def revolver_sample(con, horizon: int = HORIZON) -> pd.DataFrame:
    """Defaulted commercial revolvers: drawn and limit `horizon`
    months before default, and drawn at default.

    `facility_months` holds two rows for a facility in its month of
    default, one performing and one defaulted; the defaulted row is
    the exposure at default.
    """
    s = con.execute(f"""
        WITH d AS (
            SELECT facility_id, month AS dm, drawn_cents AS ead,
                   limit_cents AS l1
            FROM facility_months WHERE status = 'defaulted')
        SELECT d.facility_id, f.secured, d.dm AS default_month,
               m0.drawn_cents AS b0, m0.limit_cents AS l0, d.l1,
               d.ead
        FROM d JOIN facilities f USING (facility_id)
        JOIN facility_months m0 ON m0.facility_id = d.facility_id
         AND m0.status = 'performing'
         AND m0.month = last_day(d.dm - INTERVAL {int(horizon)} MONTH)
        WHERE f.kind = 'revolver'
        ORDER BY 1""").df()
    s["u0"] = s["b0"] / s["l0"]
    s["ccf"] = (s["ead"] - s["b0"]) / (s["l0"] - s["b0"])
    return s


# ------------------------------------------------------ the estimate

def save(estimates: dict, path=PARAMS) -> None:
    """Write the CCFs Ballast's later modules read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(estimates, indent=1, sort_keys=True))


def load(path=PARAMS) -> dict:
    """The CCFs saved by `save`."""
    return json.loads(path.read_text())
