"""What the market thinks of a borrower: Merton's model, the distance
to default, and the price of default risk in spreads.

For a listed company the stock market prices its shares every day,
and the shares are a claim on whatever the company's assets are worth
after its debts are paid. Merton's model reads that price backwards
to estimate what the assets are worth, how much that value moves, and
how far it is from the point where the company could not pay. The
module:

- splits each company's borrowings from its accounts and sets the
  default point (short-term debt plus half of long-term debt);
- solves Merton's two equations for asset value and asset volatility
  from equity value and equity volatility;
- turns them into a distance to default and a probability of default,
  risk-neutral or with an assumed drift;
- does it for every listed client, every month, on the accounts and
  interest rate Fernhill had at the time;
- converts credit default swap spreads into hazard rates and default
  probabilities, and Merton's model into the spread it implies.

    import fernhill
    from ballast import market as mk
    con = fernhill.connect()
    panel = mk.merton_panel(con)      # listed clients x months

Money arrives in integer cents and is turned into dollars only where
the model divides or takes logarithms.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from scipy.optimize import root
from scipy.stats import norm

from ballast.commercial import spreading as sp

# Assumptions. Each is a convention, not a fact about any company,
# and a caller can override every one.
HORIZON = 1.0              # years: the PD is a one-year PD
LONG_TERM_WEIGHT = 0.5     # default point: short + half of long
ASSET_DRIFT = None         # None: risk-neutral (the risk-free rate)
CDS_LGD = 0.60             # loss CDS quotes assume (40% recovery)
ACCOUNTS_ARRIVE = (3, 31)  # accounts reach Fernhill by 31 March


# ------------------------------------------------- the default point

def default_point(short_term, long_term, weight=LONG_TERM_WEIGHT):
    """Short-term debt plus `weight` times long-term debt."""
    return np.asarray(short_term) + weight * np.asarray(long_term)


def arrives(fy: int) -> dt.date:
    """The day a fiscal year's accounts are taken to reach Fernhill."""
    return dt.date(fy + 1, *ACCOUNTS_ARRIVE)


def default_points(con, weight=LONG_TERM_WEIGHT) -> pd.DataFrame:
    """Every listed client's debt split and default point, by fiscal
    year, with the day those accounts became available. Cents."""
    cols = ", ".join(f"f.{c}_cents AS {c}" for c in sp.RAW)
    raw = con.execute(f"""
        SELECT f.company_id, f.fiscal_year, {cols}, f.basis
        FROM financials f JOIN companies c USING (company_id)
        WHERE c.listed
        ORDER BY 1, 2""").df()
    d = sp.derive(raw)
    out = d[["company_id", "fiscal_year", "short_term_debt",
             "long_term_debt", "total_debt"]].copy()
    out["default_point"] = default_point(
        out.short_term_debt, out.long_term_debt, weight).round()
    out["available"] = [arrives(int(y)) for y in out.fiscal_year]
    return out.reset_index(drop=True)


# ------------------------------------------------ Merton's equations

def _d1_d2(V, sigma, D, r, T):
    d1 = (np.log(V / D) + (r + 0.5 * sigma ** 2) * T) \
        / (sigma * np.sqrt(T))
    return d1, d1 - sigma * np.sqrt(T)


def equity_value(V, sigma_V, D, r, T=HORIZON):
    """Equity as a call on the assets struck at the default point,
    and the equity volatility that asset volatility implies."""
    d1, d2 = _d1_d2(V, sigma_V, D, r, T)
    E = V * norm.cdf(d1) - D * np.exp(-r * T) * norm.cdf(d2)
    sigma_E = sigma_V * V * norm.cdf(d1) / E
    return E, sigma_E


def solve_assets(E, sigma_E, D, r, T=HORIZON):
    """Asset value and asset volatility from equity value, equity
    volatility, the default point and the risk-free rate: the two
    equations of `equity_value`, solved together.

    Returns (V, sigma_V, converged). Unknowns are scaled (V over
    E + D, and log volatility) so one solver suits every company.
    """
    scale = E + D

    def gap(x):
        V, s = x[0] * scale, np.exp(x[1])
        e, se = equity_value(V, s, D, r, T)
        return [e / E - 1, se / sigma_E - 1]

    V0 = E + D * np.exp(-r * T)
    x0 = [V0 / scale, np.log(sigma_E * E / V0)]
    sol = root(gap, x0, method="hybr")
    V, s = sol.x[0] * scale, float(np.exp(sol.x[1]))
    worst = max(abs(g) for g in gap(sol.x))
    ok = bool(sol.success) and worst < 1e-8
    return float(V), s, ok


def distance_to_default(V, sigma_V, D, drift, T=HORIZON):
    """How many standard deviations of a year's asset return the
    expected asset value at the horizon is above the default point."""
    return (np.log(V / D) + (drift - 0.5 * sigma_V ** 2) * T) \
        / (sigma_V * np.sqrt(T))


def default_probability(dd):
    """The model's probability that assets end below the default
    point: the normal distribution's tail beyond the distance."""
    return norm.cdf(-np.asarray(dd))


# ----------------------------------------------- spreads and hazards

def merton_spread_bps(V, sigma_V, D, r, T=HORIZON):
    """The yield spread over the risk-free rate on debt with face
    value D maturing at T, if Merton's model priced it."""
    d1, d2 = _d1_d2(V, sigma_V, D, r, T)
    value = D * np.exp(-r * T) * norm.cdf(d2) + V * norm.cdf(-d1)
    y = -np.log(value / D) / T
    return (y - r) * 1e4


def hazard_from_spread(spread_bps, lgd=CDS_LGD):
    """The annual default intensity a CDS spread implies: spread is
    roughly hazard times loss given default."""
    return np.asarray(spread_bps) / 1e4 / lgd


def pd_from_hazard(hazard, T=HORIZON):
    """Probability of default within T years at a constant hazard."""
    return 1 - np.exp(-np.asarray(hazard) * T)


# -------------------------------------------- every listed client

def risk_free(con) -> pd.Series:
    """The policy rate as a decimal, by month end: the proxy for the
    risk-free rate."""
    df = con.execute("""SELECT month, policy_rate_pct / 100 AS r
                        FROM market_rates ORDER BY month""").df()
    return pd.Series(df.r.to_numpy(), index=df.month.dt.date)


def market_months(con) -> pd.DataFrame:
    """Every listed client's month: equity value (cents), equity
    volatility, the five-year CDS spread where quoted."""
    df = con.execute("""
        SELECT company_id, month, equity_value_cents AS equity,
               equity_volatility AS sigma_e, cds_5y_bps AS cds
        FROM market_data ORDER BY company_id, month""").df()
    df["month"] = df.month.dt.date
    return df


def _attach_default_point(m: pd.DataFrame, dp: pd.DataFrame):
    """The latest default point available at each month end."""
    m = m.sort_values("month").copy()
    dp = dp.sort_values("available")
    m["_t"] = pd.to_datetime(m.month).astype("datetime64[ns]")
    dp = dp.assign(_t=pd.to_datetime(dp.available)
                   .astype("datetime64[ns]"))
    j = pd.merge_asof(m, dp[["company_id", "_t", "fiscal_year",
                             "default_point"]],
                      on="_t", by="company_id", direction="backward")
    return j.drop(columns="_t")


def merton_panel(con, weight=LONG_TERM_WEIGHT, drift=ASSET_DRIFT,
                 T=HORIZON) -> pd.DataFrame:
    """Merton's model for every listed client at every month end it
    has a share price and accounts Fernhill had received.

    Columns: company_id, month, fiscal_year (of the accounts used),
    equity and default_point (dollars), sigma_e, r, assets, sigma_a,
    converged, dd and pd (with `drift`; None means the risk-free rate,
    the risk-neutral case), cds.
    """
    m = market_months(con)
    m["r"] = m.month.map(risk_free(con))
    j = _attach_default_point(m, default_points(con, weight))
    j = j[j.default_point.notna() & (j.equity > 0)
          & (j.default_point > 0)].copy()
    j["equity"] = j.equity / 100
    j["default_point"] = j.default_point / 100
    j["fiscal_year"] = j.fiscal_year.astype(int)
    out = [solve_assets(e, s, d, r, T) for e, s, d, r in
           zip(j.equity, j.sigma_e, j.default_point, j.r)]
    j["assets"] = [o[0] for o in out]
    j["sigma_a"] = [o[1] for o in out]
    j["converged"] = [o[2] for o in out]
    mu = j.r if drift is None else drift
    j["dd"] = distance_to_default(j.assets, j.sigma_a, j.default_point,
                                  mu, T)
    j["pd"] = default_probability(j.dd)
    cols = ["company_id", "month", "fiscal_year", "equity",
            "default_point", "sigma_e", "r", "assets", "sigma_a",
            "converged", "dd", "pd", "cds"]
    return j[cols].sort_values(["company_id", "month"]) \
        .reset_index(drop=True)


def grade_in_force(con, panel: pd.DataFrame) -> pd.DataFrame:
    """Add the internal grade and the agency rating each company held
    at each month end (the latest assigned on or before it)."""
    g = con.execute("""
        SELECT company_id, rating_date, internal_grade, agency_rating
        FROM ratings ORDER BY rating_date""").df()
    out = panel.sort_values("month").copy()
    out["_t"] = pd.to_datetime(out.month).astype("datetime64[ns]")
    g["rating_date"] = g.rating_date.astype("datetime64[ns]")
    for col in ("internal_grade", "agency_rating"):
        side = g[g[col].notna()][["company_id", "rating_date", col]]
        side = side.rename(columns={"rating_date": "_t"})
        out = pd.merge_asof(out, side.sort_values("_t"), on="_t",
                            by="company_id", direction="backward")
    return out.drop(columns="_t").sort_values(
        ["company_id", "month"]).reset_index(drop=True)
