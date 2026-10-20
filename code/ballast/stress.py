"""Stress testing: Fernhill's book through a hard three years.

A stress test asks what a named, severe path of the economy would do
to the lender: how many borrowers would default, what the losses and
provisions would be, what would be earned meanwhile, and where the
capital ratio would bottom out. This module does it for the book as
it stood on 31 December 2025, year by year to 2028:

- **paths**: the scenarios published for the reporting date (with
  the supervisor's `stress_2026`), a past episode replayed from
  today's starting point (`historical`), or a scaled stress
  (`scaled`, for the reverse stress test);
- **satellite models**: each product's yearly default rate on the
  economy, 2017 to 2025, the top-down check on the engine; and the
  two drivers Chapter 18's hazards do not see, measured here: the
  payment shock on mortgages and interest rates for companies;
- **projection**: on a static balance sheet (every loan that
  defaults or repays is replaced by one like it), each year's
  defaults and losses from Chapter 20's engine under the path, LGDs
  moved by house and car prices and by cure rates, the provision at
  each year end as Fernhill would measure it then, net interest
  income, RWA both ways, and the CET1 ratio;
- **reverse stress**: how far the stress must be scaled for the
  CET1 ratio to touch the requirement.

    import fernhill
    from ballast import stress
    con = fernhill.connect()
    inp = stress.inputs(con)
    res = stress.project(inp, stress.paths(con)["stress_2026"])
    res["years"]                     # one row a year: losses to CET1

Every estimate is made on the loan book; nothing is read from the
truth. Results are saved under data/ballast/stress/.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm

from ballast import capital, ecl
from ballast import performance as perf
from ballast.config import AS_OF, BALLAST, ROOT
from ballast.parameters import lgd as lgdm
from ballast.parameters import pd as pdm

# ------------------------------------------------- Fernhill's choices
YEARS = (2026, 2027, 2028)         # the stress horizon
SCENARIOS = ("base", "severe", "stress_2026")
DOWNTURN_GAP = 1.0      # downturn LGD in a year whose unemployment is
                        # a point or more above the decade's average
CURE_U = -0.086         # Chapter 25: log odds of a cure, per point
CURED = ("personal", "card", "sme_overdraft")   # cure-driven LGDs
FORCED_SALE = 0.20      # a repossessed home sells this far below
                        # its indexed value (an assumption)
SALE_COST = 0.05        # costs of a mortgage workout, share of EAD
CAR_LINE = (0.055, 0.419)          # Chapter 19: LGD on indexed LTV
FTV_MARGIN = 2.5        # fixed-then-variable revert to policy + 2.5
COST_SHARE = 0.5        # operating costs: half of 2025's NII, flat
SATELLITE_YEARS = range(2017, 2026)
SATELLITE_PRODUCTS = ("personal", "card", "auto", "mortgage",
                      "sme_term", "sme_overdraft", "commercial")
OUT = BALLAST / "stress"
COLS = ["u", "policy", "hpi", "car", "gdp"]


# --------------------------------------------------------------- paths

def history(con) -> pd.DataFrame:
    """The monthly macro history, in the columns paths use."""
    return con.execute("""
        SELECT month, unemployment_pct AS u, policy_rate_pct AS policy,
               house_price_index AS hpi, used_car_index AS car,
               gdp_growth_pct AS gdp
        FROM macro ORDER BY month""").df()


def paths(con, names=None) -> dict:
    """Each scenario published for 31 December 2025, as a monthly path
    from January 2026 to December 2030."""
    s = con.execute("""
        SELECT scenario, month, unemployment_pct AS u,
               policy_rate_pct AS policy, house_price_index AS hpi,
               used_car_index AS car, gdp_growth_pct AS gdp
        FROM scenarios WHERE as_of = ? ORDER BY scenario, month""",
                    [AS_OF]).df()
    out = {k: g.drop(columns="scenario").reset_index(drop=True)
           for k, g in s.groupby("scenario")}
    return {k: out[k] for k in (names or out)}


def start(con) -> dict:
    """The economy on the reporting date."""
    h = history(con)
    return h[h.month == pd.Timestamp(AS_OF)].iloc[0][COLS].to_dict()


def historical(con, first: str, months: int = 36) -> pd.DataFrame:
    """A past episode replayed from today: the changes in each macro
    series over `months` months from `first`, measured from the month
    before, added to (rates, unemployment) or multiplied into (price
    indices) the levels of December 2025, then held for the rest of
    the five years. The policy rate cannot go below zero."""
    h = history(con).set_index("month")
    i = h.index.get_loc(pd.Timestamp(first))
    base, ep = h.iloc[i - 1], h.iloc[i:i + months]
    s0 = start(con)
    out = pd.DataFrame({
        "u": s0["u"] + ep.u.to_numpy() - base.u,
        "policy": np.maximum(s0["policy"] + ep.policy.to_numpy()
                             - base.policy, 0.0),
        "hpi": s0["hpi"] * ep.hpi.to_numpy() / base.hpi,
        "car": s0["car"] * ep.car.to_numpy() / base.car,
        "gdp": ep.gdp.to_numpy()})
    out = pd.concat([out, out.iloc[[-1] * (60 - len(out))]],
                    ignore_index=True)
    out.insert(0, "month", pd.date_range("2026-01-31", periods=60,
                                         freq="ME"))
    return out


def scaled(path: pd.DataFrame, s0: dict, k: float,
           what=("u", "hpi", "car")) -> pd.DataFrame:
    """A path whose departures from today's levels are `k` times the
    given path's, for the series in `what` (the rest unchanged)."""
    out = path.copy()
    for c in what:
        if c in ("hpi", "car"):
            out[c] = s0[c] * (1 + k * (path[c] / s0[c] - 1))
        else:
            out[c] = s0[c] + k * (path[c] - s0[c])
    return out


def annual(path: pd.DataFrame) -> pd.DataFrame:
    """Each year's average unemployment and policy rate, and the
    year-end price indices, for the first three years of a path."""
    p = path.iloc[:12 * len(YEARS)].copy()
    p["year"] = np.repeat(YEARS, 12)
    g = p.groupby("year")
    return pd.DataFrame({"u": g.u.mean(), "policy": g.policy.mean(),
                         "u_end": g.u.last(), "policy_end":
                         g.policy.last(), "hpi": g.hpi.last(),
                         "car": g.car.last(), "gdp": g.gdp.mean()})


# ---------------------------------------------------- satellite models

def default_history(con) -> pd.DataFrame:
    """Each product's yearly default rate (Chapter 18's measure; for
    the commercial book, clients with a performing facility at the
    year's start and a default during it), with the year's average
    unemployment and policy rate and the change in the price
    indices."""
    eps = perf.default_episodes(con, pdm.DEFINITION)
    retail = [p for p in SATELLITE_PRODUCTS if p != "commercial"]
    r = pdm.annual_default_rates(con, eps, retail, SATELLITE_YEARS)
    c = con.execute("""
        WITH fy AS (
            SELECT DISTINCT f.company_id, year(fm.month) + 1 AS year
            FROM facility_months fm
            JOIN facilities f USING (facility_id)
            WHERE month(fm.month) = 12 AND fm.status = 'performing'),
        d AS (SELECT company_id, year(default_month) AS year
              FROM corporate_defaults)
        SELECT fy.year, 'commercial' AS product, count(*) AS at_risk,
               count(d.company_id) AS defaults
        FROM fy LEFT JOIN d USING (company_id, year)
        GROUP BY 1 ORDER BY 1""").df()
    c = c[c.year.isin(list(SATELLITE_YEARS))]
    out = pd.concat([r[["year", "product", "at_risk", "defaults"]], c],
                    ignore_index=True)
    out["rate"] = out.defaults / out.at_risk
    h = history(con)
    h["year"] = h.month.dt.year
    g = h.groupby("year")
    m = pd.DataFrame({"u": g.u.mean(), "policy": g.policy.mean(),
                      "hpi": g.hpi.last(), "car": g.car.last()})
    m["hpi_chg"] = m.hpi.pct_change()
    m["car_chg"] = m.car.pct_change()
    return out.merge(m[["u", "policy", "hpi_chg", "car_chg"]],
                     left_on="year", right_index=True)


def fit_satellite(h: pd.DataFrame, product: str, drivers=("u",),
                  drop_years=()) -> dict:
    """A logistic regression of one product's yearly default rate on
    the drivers, weighted by accounts at risk. Its standard errors
    are scaled for overdispersion: the years, not the accounts, are
    the observations, and nine of them disagree more than chance
    among thousands of accounts would allow."""
    g = h[(h["product"] == product) & ~h.year.isin(list(drop_years))]
    X = sm.add_constant(g[list(drivers)].astype(float))
    m = sm.GLM(g.rate.astype(float), X, family=sm.families.Binomial(),
               var_weights=g.at_risk.astype(float)).fit(scale="X2")
    return {"product": product, "drivers": list(drivers),
            "params": m.params.to_dict(), "bse": m.bse.to_dict(),
            "cov": m.cov_params().to_numpy().tolist(),
            "scale": float(m.scale), "years": len(g)}


def satellite_rate(fit: dict, x: dict, z: float = 1.645) -> tuple:
    """A satellite model's default rate at the driver values `x`,
    with a two-sided interval (90% by default) for the line."""
    names = ["const"] + fit["drivers"]
    v = np.array([1.0] + [x[d] for d in fit["drivers"]])
    b = np.array([fit["params"][n] for n in names])
    eta = float(v @ b)
    se = float(np.sqrt(v @ np.array(fit["cov"]) @ v))
    f = lambda e: 1 / (1 + np.exp(-e))         # noqa: E731
    return f(eta), f(eta - z * se), f(eta + z * se)


# ------------------------------------------------- the payment shock

def payment_panel(con) -> pd.DataFrame:
    """Every mortgage at every quarter end from December 2017 to
    December 2024, open, at most two payments behind and not on a
    holiday: its payment against its first payment, and whether a
    default began in the next twelve months."""
    eps = perf.default_episodes(con, pdm.DEFINITION)
    con.register("st_eps", eps[["account_id", "default_month"]])
    d = con.execute("""
        SELECT p.account_id, p.month, p.missed,
               ln(greatest(p.scheduled_cents / a.payment_cents, 1))
                   AS shock,
               m.unemployment_pct AS u,
               EXISTS (SELECT 1 FROM st_eps e
                       WHERE e.account_id = p.account_id
                         AND e.default_month > p.month
                         AND e.default_month
                             <= p.month + INTERVAL 12 MONTH) AS y
        FROM performance p JOIN accounts a USING (account_id)
        JOIN macro m ON m.month = p.month
        WHERE p.product = 'mortgage' AND month(p.month) % 3 = 0
          AND p.month BETWEEN DATE '2017-12-31' AND DATE '2024-12-31'
          AND p.status IN ('up_to_date', 'arrears') AND p.missed <= 2
          AND NOT p.payment_holiday
        ORDER BY 1, 2""").df()
    con.unregister("st_eps")
    d["y"] = d.y.astype(int)
    return d


def fit_payment_shock(panel: pd.DataFrame) -> dict:
    """Log odds of default per unit of log(payment / first payment),
    holding arrears and unemployment fixed."""
    X = pd.DataFrame({"const": 1.0, "shock": panel.shock,
                      "missed_1": (panel.missed == 1).astype(float),
                      "missed_2": (panel.missed == 2).astype(float),
                      "u": panel.u})
    m = sm.Logit(panel.y, X).fit(disp=0)
    return {"params": m.params.to_dict(), "bse": m.bse.to_dict(),
            "n": int(len(panel)), "defaults": int(panel.y.sum())}


def annuity(balance, rate_pct, months) -> np.ndarray:
    """The level payment that repays `balance` over `months`."""
    r = np.asarray(rate_pct, dtype=float) / 1200
    n = np.maximum(np.asarray(months, dtype=float), 1)
    b = np.asarray(balance, dtype=float)
    safe = np.where(r > 0, r, 1)
    return np.where(r > 0, b * safe / (1 - (1 + safe) ** -n), b / n)


def mortgage_rates(m: pd.DataFrame, policy: float, month: int,
                   policy0: float) -> np.ndarray:
    """Each mortgage's rate when the policy rate is `policy`, `month`
    months after December 2025: fixed loans keep theirs; variable
    loans move with the policy rate; fixed-then-variable loans keep
    theirs until the fix ends and then pay policy + 2.5."""
    r0 = m.rate_pct.to_numpy()
    var = r0 + policy - policy0
    ftv_now = np.where(m.fix_end.to_numpy() <= 0, var, r0)
    ftv = np.where(m.fix_end.to_numpy() <= month, np.where(
        m.fix_end.to_numpy() <= 0, var, policy + FTV_MARGIN), ftv_now)
    return np.select([m.rate_type == "variable",
                      m.rate_type == "fixed_then_variable"],
                     [var, ftv], r0)


# ------------------------------------------------------------ inputs

def _mortgages(con, rb: pd.DataFrame) -> pd.DataFrame:
    m = con.execute("""
        SELECT a.account_id, a.rate_type, a.payment_cents AS pay0,
               a.collateral_value_cents
                 * (SELECT house_price_index FROM macro WHERE month = ?)
                 / h.house_price_index AS value_cents,
               date_diff('month', ?::DATE,
                         a.open_date + to_months(
                             coalesce(a.fixed_months, 0)::INT))
                   AS fix_end
        FROM accounts a JOIN macro h
          ON h.month = last_day(a.open_date)
        WHERE a.product = 'mortgage' ORDER BY 1""",
                    [AS_OF, AS_OF]).df()
    cols = ["account_id", "balance_cents", "rate_pct", "remaining",
            "in_default"]
    return rb[rb["product"] == "mortgage"][cols].merge(
        m, on="account_id", how="left").reset_index(drop=True)


def _cars(con, rb: pd.DataFrame) -> pd.DataFrame:
    c = con.execute("""
        SELECT a.account_id,
               a.collateral_value_cents
                 * (SELECT used_car_index FROM macro WHERE month = ?)
                 / h.used_car_index AS value_cents
        FROM accounts a JOIN macro h ON h.month = last_day(a.open_date)
        WHERE a.product = 'auto' ORDER BY 1""", [AS_OF]).df()
    return rb[rb["product"] == "auto"][["account_id", "balance_cents",
                                        "in_default"]].merge(
        c, on="account_id", how="left").reset_index(drop=True)


def pass_through(con) -> dict:
    """How far each floating product's rate moved with the policy
    rate: the median change in rate on accounts open at both December
    2021 and December 2023, over the policy rate's rise."""
    r = con.execute("""
        WITH a AS (SELECT account_id, product, rate_pct FROM performance
                   WHERE month = DATE '2021-12-31'),
             b AS (SELECT coalesce(c.predecessor_id, p.account_id)
                              AS account_id, p.rate_pct
                   FROM performance p JOIN accounts c USING (account_id)
                   WHERE p.month = DATE '2023-12-31')
        SELECT a.product, median(b.rate_pct - a.rate_pct)
        FROM a JOIN b USING (account_id)
        WHERE a.product IN ('card', 'sme_overdraft', 'sme_term')
        GROUP BY 1 ORDER BY 1""").fetchall()
    rise = con.execute("""
        SELECT max(policy_rate_pct) FILTER (WHERE month = '2023-12-31')
             - max(policy_rate_pct) FILTER (WHERE month = '2021-12-31')
        FROM market_rates""").fetchone()[0]
    return {p: float(x) / rise for p, x in r}


def funding(con) -> tuple:
    """Fernhill's cost of funds as a straight line in the policy
    rate, fitted on every month of the decade: (intercept, slope)."""
    d = con.execute("SELECT policy_rate_pct, cost_of_funds_pct "
                    "FROM market_rates ORDER BY month").df()
    b, a = np.polyfit(d.policy_rate_pct, d.cost_of_funds_pct, 1)
    return float(a), float(b)


def inputs(con) -> dict:
    """Everything a projection needs, estimated once: Chapter 20's
    parameters and books, Chapter 21's saved capital run, the
    collateral, the floating rates and the two overlays."""
    params = ecl.parameters(con)
    rb = ecl.retail_book(con)
    cb = ecl.commercial_book(con)
    rb["segment"], cb["segment"] = "retail", "commercial"
    rb["grade"] = np.nan
    cbx = cb.rename(columns={"defaulted": "in_default"})
    cbx["missed"], cbx["cured"] = 0, False
    book = pd.concat([rb, cbx], ignore_index=True)
    shock = fit_payment_shock(payment_panel(con))
    h = default_history(con)
    corp = fit_satellite(h, "commercial", ("u", "policy"))
    cap = capital.load()
    k = capital.bank_capital(con)
    s0 = start(con)
    cof_now = con.execute("SELECT cost_of_funds_pct FROM market_rates "
                          "WHERE month = ?", [AS_OF]).fetchone()[0]
    inp = {"params": params, "rb": rb, "cb": cb, "book": book,
           "mortgages": _mortgages(con, rb), "cars": _cars(con, rb),
           "cure": {p: v["cure_rate"]
                    for p, v in lgdm.load()["products"].items()},
           "shock_beta": shock["params"]["shock"],
           "rate_beta": corp["params"]["policy"],
           "corp_u_beta": corp["params"]["u"],
           "pass": pass_through(con), "funding": funding(con),
           "cof_now": float(cof_now), "capital": cap, "bank": k,
           "start": s0, "base_set": params["scenarios"].copy()}
    inp["nii0"] = nii(inp, s0["policy"], 0.0, cof=inp["cof_now"])
    inp["prov0"] = provision(inp, None)["total"]
    return inp


# ---------------------------------------------------------- overlays

def _odds(p, mult):
    p = np.clip(np.asarray(p, dtype=float), 0, 0.999999)
    return mult * p / (1 - p + mult * p)


def overlay(inp: dict, account_id, policy: float, month: int
            ) -> np.ndarray:
    """Each account's multiplier on the odds of default for the
    payment shock, which the engine does not see: a mortgage's
    payment at the policy rate `policy`, `month` months on, against
    its payment today, through the coefficient of
    `fit_payment_shock`. Every other account's is 1."""
    ids = pd.Index(account_id)
    m = inp["mortgages"]
    p0 = inp["start"]["policy"]
    now = annuity(m.balance_cents, m.rate_pct, m.remaining)
    new = annuity(m.balance_cents, mortgage_rates(m, policy, month, p0),
                  m.remaining)
    s_now = np.log(np.maximum(now / m.pay0, 1))
    s_new = np.log(np.maximum(new / m.pay0, 1))
    out = pd.Series(np.exp(inp["shock_beta"] * (s_new - s_now)),
                    index=m.account_id).reindex(ids).fillna(1.0)
    return out.to_numpy()


def corp_path(inp: dict, u, policy, corp_u: float | None = None
              ) -> np.ndarray:
    """The unemployment path to give the commercial projection so that
    it also carries interest rates. Chapter 20's commercial PD moves
    each year's odds by exp(b x (unemployment - long run)); adding
    (c / b) x (policy rate - today's) to unemployment adds the
    satellite model's exp(c x (policy rate - today's)) to the same
    odds, year by year. `corp_u` replaces b with another sensitivity
    (a test of how much the answer depends on it)."""
    beta = inp["params"]["hazards"]["sme_term"].default["u"]
    u = np.asarray(u, dtype=float)
    r = np.asarray(policy, dtype=float)
    out = u + inp["rate_beta"] / beta * (r - inp["start"]["policy"])
    if corp_u is not None:
        out = out + (corp_u - beta) / beta * (u - inp["params"]
                                              ["long_run_u"])
    return out


def _extend(x, n: int) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return np.r_[x, np.repeat(x[-1], max(n - len(x), 0))][:n]


# --------------------------------------------------------------- LGDs

def mortgage_model(inp: dict, hpi: float) -> float:
    """The mortgage book's LGD (EAD-weighted, cures included) if house
    prices stood at `hpi`, from each performing loan's indexed
    loan-to-value: one less the cure rate, times the costs of the
    workout plus whatever the home, sold 20% below its indexed value,
    fails to cover."""
    m = inp["mortgages"][~inp["mortgages"].in_default.astype(bool)]
    ead = m.balance_cents.to_numpy(dtype=float)
    v = m.value_cents.to_numpy() * hpi / inp["start"]["hpi"]
    short = np.maximum(ead - (1 - FORCED_SALE) * v, 0) / ead
    cure = inp["cure"]["mortgage"]
    return float(((1 - cure) * (SALE_COST + short) * ead).sum()
                 / ead.sum())


def mortgage_lgd(inp: dict, hpi: float) -> float:
    """`mortgage_model` as a ratio to its value at today's prices,
    times the LGD Chapter 20 measured, so that today's index gives
    today's LGD."""
    base = inp["params"]["lgd"].loc["mortgage", "lgd"]
    return base * mortgage_model(inp, hpi) / mortgage_model(
        inp, inp["start"]["hpi"])


def car_lgd(inp: dict, car: float) -> float:
    """The car book's LGD if used-car prices stood at `car`: Chapter
    19's line in indexed loan-to-value, as a ratio to today's, times
    the LGD Chapter 20 measured."""
    c = inp["cars"][~inp["cars"].in_default.astype(bool)]
    ead = c.balance_cents.to_numpy(dtype=float)

    def line(index):
        ltv = ead / (c.value_cents.to_numpy() * index
                     / inp["start"]["car"])
        return float(((CAR_LINE[0] + CAR_LINE[1] * ltv) * ead).sum()
                     / ead.sum())
    base = inp["params"]["lgd"].loc["auto", "lgd"]
    return base * line(car) / line(inp["start"]["car"])


def cure_lgd(inp: dict, product: str, u: float) -> float:
    """An unsecured product's LGD when unemployment is `u`: the loss
    without a cure times one less the cure rate, which falls with
    unemployment by Chapter 25's coefficient."""
    base = inp["params"]["lgd"].loc[product, "lgd"]
    c0 = inp["cure"][product]
    eta = np.log(c0 / (1 - c0)) + CURE_U * (u - inp["start"]["u"])
    c = 1 / (1 + np.exp(-eta))
    return base / (1 - c0) * (1 - c)


def lgd_table(inp: dict, u: float, hpi: float, car: float,
              downturn: bool | None = None) -> pd.DataFrame:
    """Chapter 20's LGD table with house and car prices, and cures at
    unemployment `u`, applied; and a column `year` that is the
    downturn LGD in a downturn year and the long-run one otherwise."""
    t = inp["params"]["lgd"].copy()
    for col in ("lgd", "downturn"):
        t.loc["mortgage", col] = max(t.loc["mortgage", col],
                                     mortgage_lgd(inp, hpi))
        t.loc["auto", col] = max(t.loc["auto", col], car_lgd(inp, car))
        for p in CURED:
            t.loc[p, col] = max(t.loc[p, col], cure_lgd(inp, p, u))
    if downturn is None:
        downturn = u >= inp["params"]["long_run_u"] + DOWNTURN_GAP
    t["year"] = t["downturn"] if downturn else t["lgd"]
    return t


# ---------------------------------------------------------- provision

def provision(inp: dict, at: dict | None, corp_u=None) -> dict:
    """The provision Fernhill would book on a year end of the stress,
    on the static book. Its economists' central path is taken to be
    the stress path from that date on (`at["fwd"]` and
    `at["fwd_policy"]`, monthly), and their four scenarios keep the
    spread around the central path that the December 2025 set has
    around its base, so that a base path reproduces the booked
    provision. LGDs are at that date's prices and at the cure rates
    of the year ahead's unemployment (`at["u"]`); the payment shock
    at the year ahead's policy rate (`at["policy"]`). `at` is None
    for the reporting date itself."""
    p = dict(inp["params"])
    s0 = inp["start"]
    sc = inp["base_set"].copy()
    corp = sc.copy()
    if at is None:
        at = {"u": s0["u"], "policy": s0["policy"], "hpi": s0["hpi"],
              "car": s0["car"], "month": 0}
    else:
        base = sc.loc["base", "path"]
        n = len(base)
        f = _extend(at["fwd"], n)
        r = _extend(at["fwd_policy"], n)
        sc["path"] = [f + (x - base) for x in sc.path]
        corp["path"] = [corp_path(inp, x, r, corp_u) for x in sc.path]
    p["lgd"] = lgd_table(inp, at["u"], at["hpi"], at["car"])
    pc = dict(p, scenarios=corp)
    p["scenarios"] = sc
    book = inp["book"]
    proj = pd.concat([ecl.project_retail(inp["rb"], p),
                      ecl.project_commercial(inp["cb"], pc)])
    b = book.merge(proj, on="account_id", how="left")
    mult = overlay(inp, b.account_id, at["policy"], at["month"])
    w = sc["weight"]
    for s in ecl.WEIGHTED:
        old = b[f"pd12_{s}"].to_numpy()
        new = _odds(old, mult)
        ratio = np.where(old > 0, new / np.where(old > 0, old, 1), 1)
        b[f"pd12_{s}"] = new
        for col in (f"ecl12_{s}", f"ecllife_{s}"):
            b[col] = b[col] * ratio
    b["pd12"] = sum(w[s] * b[f"pd12_{s}"] for s in ecl.WEIGHTED)
    b = pd.concat([b, ecl.stage(b)], axis=1)
    d = b["in_default"].fillna(False).to_numpy(dtype=bool)
    key = np.where(b["segment"] == "retail", b["product"],
                   np.where(b["secured"].fillna(False),
                            "commercial_secured",
                            "commercial_unsecured"))
    total = np.zeros(len(b))
    for s in ecl.WEIGHTED:
        lgd = p["lgd"][sc.loc[s, "lgd"]].reindex(key).to_numpy()
        val = np.where(b.stage == 1, b[f"ecl12_{s}"], b[f"ecllife_{s}"])
        val = np.where(b.stage == 3, b.balance_cents * lgd, val)
        total += w[s] * np.nan_to_num(val)
    b["ecl"] = total
    b.loc[d, "pd12"] = 1.0
    st = b.groupby("stage").agg(n=("ecl", "size"),
                                bal=("balance_cents", "sum"),
                                ecl=("ecl", "sum"))
    return {"total": float(total.sum()), "stages": st,
            "by_product": b.groupby("product")["ecl"].sum(),
            "accounts": b[["account_id", "product", "stage", "pd12",
                           "ecl"]]}


# -------------------------------------------------- income and capital

def nii(inp: dict, policy: float, lost_cents: float = 0.0,
        cof: float | None = None, month: int = 0) -> float:
    """A year's net interest income on the static book at an average
    policy rate: fixed loans keep their rates, floating products move
    with the policy rate at their measured pass-through, mortgages as
    `mortgage_rates`, companies pay the policy rate plus their
    margin; funding costs the line in `funding` on everything not
    funded by CET1; defaulted loans earn nothing (`lost_cents` is the
    interest given up on the year's defaults)."""
    rb, cb, p0 = inp["rb"], inp["cb"], inp["start"]["policy"]
    perf_ = rb[~rb.in_default.astype(bool)]
    rate = perf_.rate_pct.to_numpy().copy()
    for prod, k in inp["pass"].items():
        sel = (perf_["product"] == prod).to_numpy()
        rate[sel] += k * (policy - p0)
    m = inp["mortgages"]
    mr = pd.Series(mortgage_rates(m, policy, month, p0),
                   index=m.account_id)
    sel = (perf_["product"] == "mortgage").to_numpy()
    rate[sel] = mr.reindex(perf_.account_id[sel]).to_numpy()
    income = float((perf_.balance_cents * rate).sum()) / 100
    c = cb[~cb.defaulted.astype(bool)]
    income += float((c.balance_cents * (c.rate_pct + policy - p0))
                    .sum()) / 100
    drawn = float(rb.balance_cents.sum() + cb.balance_cents.sum())
    if cof is None:
        a, b = inp["funding"]
        cof = a + b * policy
        cof += inp["cof_now"] - (a + b * p0)    # anchored to today
    cost = (drawn - inp["bank"]["cet1"]) * cof / 100
    return income - cost - lost_cents


def capital_rows(inp: dict, pd12: pd.Series, cet1: float,
                 prov: float) -> dict:
    """RWA and ratios at a year end: standardised (unchanged on a
    static book) and IRB with each performing account's PD raised to
    its stressed 12-month PD where that is higher than its
    through-the-cycle PD; the CET1 ratio on each."""
    r = inp["capital"].copy()
    k = inp["bank"]
    other = k["operational_rwa"] + k["market_rwa"]
    sa = float(r.sa_rwa.sum()) + other
    stressed = r.account_id.map(pd12).to_numpy(dtype=float)
    d = r.in_default.astype(bool).to_numpy()
    r["pd"] = np.where(d | np.isnan(stressed), r["pd"],
                       np.maximum(r["pd"], np.nan_to_num(stressed)))
    r = capital.irb(r)
    irb_total = capital.output_floor(float(r.irb_rwa.sum()) + other, sa)
    gap = prov - float(r.el.sum())
    cap = dict(k, cet1=cet1)
    return {"sa_rwa": sa, "irb_rwa": irb_total,
            "cet1_sa": cet1 / sa,
            "cet1_irb": capital.ratios(cap, irb_total, gap,
                                       float(r.irb_rwa.sum()))["cet1"],
            "el": float(r.el.sum())}


# --------------------------------------------------------- projection

def _year_pd(inp: dict, path: pd.DataFrame, t: int, lgd: pd.DataFrame,
             policy: float, corp_u=None) -> pd.DataFrame:
    """Each performing account's 12-month PD from the start of year t
    along the path itself, with the payment shock at the year's
    average policy rate (`policy`) and companies' rates carried in
    their unemployment path; its EAD; its LGD."""
    p = dict(inp["params"])
    seg = path.iloc[12 * (t - 1):]
    one = {"weight": [1.0], "lgd": ["year"]}
    p["lgd"] = lgd
    p["scenarios"] = pd.DataFrame(dict(one, path=[seg.u.to_numpy()]),
                                  index=["path"])
    pc = dict(p, scenarios=pd.DataFrame(dict(one, path=[corp_path(
        inp, seg.u, seg.policy, corp_u)]), index=["path"]))
    rb = inp["rb"][~inp["rb"].in_default.astype(bool)]
    proj = pd.concat([ecl.project_retail(rb, p),
                      ecl.project_commercial(inp["cb"], pc)])
    b = inp["book"][["account_id", "product", "segment", "secured",
                     "rate_pct"]].merge(proj, on="account_id")
    mult = overlay(inp, b.account_id, policy, 12 * t - 6)
    b["pd"] = _odds(b.pd12_path, mult)
    key = np.where(b["segment"] == "retail", b["product"],
                   np.where(b["secured"].fillna(False),
                            "commercial_secured",
                            "commercial_unsecured"))
    b["lgd"] = lgd["year"].reindex(key).to_numpy()
    b["default_ead"] = b["pd"] * b["ead_cents"]
    b["loss"] = b["default_ead"] * b["lgd"]
    return b[["account_id", "product", "pd", "ead_cents", "lgd",
              "default_ead", "loss", "rate_pct"]]


def project(inp: dict, path: pd.DataFrame, name: str = "",
            corp_u: float | None = None, overlays: bool = True) -> dict:
    """Three years of a path on the static book. Returns `years` (one
    row a year: the economy, defaults, losses, the provision and its
    stages, the impairment charge, net interest income, costs, CET1,
    RWA both ways and the CET1 ratios) and `products` (defaults and
    losses by product and year)."""
    if not overlays:
        inp = dict(inp, shock_beta=0.0, rate_beta=0.0)
    a = annual(path)
    k = inp["bank"]
    cet1, prov_prev = float(k["cet1"]), inp["prov0"]
    cost = COST_SHARE * inp["nii0"]
    years, prods = [], []
    for t, y in enumerate(YEARS, start=1):
        row = a.loc[y]
        lg = lgd_table(inp, row.u, row.hpi, row.car)
        acc = _year_pd(inp, path, t, lg, row.policy, corp_u)
        lost = float((acc.default_ead * acc.rate_pct).sum()) / 100 / 2
        income = nii(inp, row.policy, lost, month=12 * t - 6)
        fwd = path.iloc[12 * t:]
        at = {"fwd": fwd.u.to_numpy(), "fwd_policy":
              fwd.policy.to_numpy(), "u": fwd.u.iloc[:12].mean(),
              "policy": fwd.policy.iloc[:12].mean(), "hpi": row.hpi,
              "car": row.car, "month": 12 * t + 6}
        pv = provision(inp, at, corp_u)
        loss = float(acc.loss.sum())
        charge = loss + pv["total"] - prov_prev
        cet1 = cet1 + income - cost - charge
        caprow = capital_rows(inp, acc.set_index("account_id")["pd"],
                              cet1, pv["total"])
        st = pv["stages"]
        years.append({
            "scenario": name, "year": y, "u": row.u,
            "policy": row.policy, "hpi": row.hpi, "car": row.car,
            "defaults": float(acc.pd.sum()),
            "default_ead": float(acc.default_ead.sum()), "loss": loss,
            "provision": pv["total"],
            "stage2": int(st.n.get(2, 0)),
            "stage2_bal": float(st.bal.get(2, 0)),
            "charge": charge, "nii": income, "cost": cost,
            "profit": income - cost - charge, "cet1": cet1, **caprow})
        g = acc.groupby("product").agg(
            defaults=("pd", "sum"), default_ead=("default_ead", "sum"),
            loss=("loss", "sum"), ead=("ead_cents", "sum"))
        g["lgd"] = g.loss / g.default_ead
        g["rate"] = g.defaults / acc.groupby("product").size()
        g["provision"] = pv["by_product"].reindex(g.index)
        g = g.reset_index()
        g.insert(0, "year", y)
        g.insert(0, "scenario", name)
        prods.append(g)
        prov_prev = pv["total"]
    yr = pd.DataFrame(years)
    return {"years": yr,
            "products": pd.concat(prods, ignore_index=True),
            "trough_sa": float(yr.cet1_sa.min()),
            "trough_irb": float(yr.cet1_irb.min())}


def year_zero(inp: dict) -> dict:
    """The starting point on 31 December 2025, in `project`'s terms,
    with the income assumptions a projection used."""
    k = inp["bank"]
    r = inp["capital"]
    other = k["operational_rwa"] + k["market_rwa"]
    sa = float(r.sa_rwa.sum()) + other
    return {"year": 2025, "provision": inp["prov0"],
            "cet1": float(k["cet1"]), "sa_rwa": sa,
            "cet1_sa": k["cet1"] / sa, "nii": inp["nii0"],
            "cost": COST_SHARE * inp["nii0"], "pass": inp["pass"],
            "funding": list(inp["funding"]),
            "cof_now": inp["cof_now"],
            "drawn": float(inp["rb"].balance_cents.sum()
                           + inp["cb"].balance_cents.sum()),
            "shock_beta": inp["shock_beta"],
            "rate_beta": inp["rate_beta"]}


# ------------------------------------------------------------ reverse

def reverse(inp: dict, path: pd.DataFrame, target: float | None = None,
            lo: float = 1.0, hi: float = 4.0, tol: float = 0.0005,
            what=("u", "hpi", "car"), steps: int = 12) -> dict:
    """The multiple of a path's departures from today (unemployment
    and prices by default) at which the lowest standardised CET1
    ratio of the three years equals `target` (the requirement with
    buffers, by default). The multiple is found by false position
    (the Illinois form): each step draws a straight line between the
    two multiples that bracket the answer, so it needs a few full
    projections rather than a dozen."""
    if target is None:
        target = capital.requirements()["cet1"]
    s0 = inp["start"]
    tried = []

    def f(k):
        res = project(inp, scaled(path, s0, k, what), f"x{k:.4f}")
        tried.append((k, res["trough_sa"]))
        return res["trough_sa"] - target, res

    fa, _ = f(lo)
    fb, res = f(hi)
    if fa * fb > 0:
        raise ValueError("the multiples do not bracket the target")
    side, k = 0, hi
    for _ in range(steps):
        k = (lo * fb - hi * fa) / (fb - fa)
        fk, res = f(k)
        if abs(fk) < tol:
            break
        if fk * fb > 0:              # replaces the upper end
            hi, fb = k, fk
            if side == -1:
                fa /= 2
            side = -1
        else:                        # replaces the lower end
            lo, fa = k, fk
            if side == 1:
                fb /= 2
            side = 1
    p = scaled(path, s0, k, what)
    return {"k": k, "trough_sa": res["trough_sa"],
            "peak_u": float(p.u.max()),
            "peak_policy": float(p.policy.max()),
            "hpi_fall": float(p.hpi.min() / s0["hpi"] - 1),
            "car_fall": float(p.car.min() / s0["car"] - 1),
            "result": res, "steps": tried, "target": target}


# ------------------------------------------------------------- saving

def save(results: dict, paths_: dict, extra: dict | None = None
         ) -> list[str]:
    """Write the projections (one row a year, and by product), the
    paths they ran on, and any extra numbers (the reverse stress)
    under data/ballast/stress/."""
    OUT.mkdir(parents=True, exist_ok=True)
    yr = pd.concat([r["years"] for r in results.values()])
    pr = pd.concat([r["products"] for r in results.values()])
    pa = pd.concat([p.assign(scenario=k) for k, p in paths_.items()])
    files = {"years": OUT / f"years_{AS_OF}.csv",
             "products": OUT / f"products_{AS_OF}.csv",
             "paths": OUT / f"paths_{AS_OF}.csv"}
    yr.round(6).to_csv(files["years"], index=False)
    pr.round(6).to_csv(files["products"], index=False)
    pa.round({c: 4 for c in COLS}).to_csv(files["paths"], index=False)
    files["summary"] = OUT / f"summary_{AS_OF}.json"
    files["summary"].write_text(json.dumps({
        "as_of": str(AS_OF), "requirement": capital.requirements()
        ["cet1"], "trough_sa": {k: r["trough_sa"]
                                for k, r in results.items()},
        "trough_irb": {k: r["trough_irb"] for k, r in results.items()},
        **(extra or {})}, indent=1) + "\n")
    return [str(f.relative_to(ROOT)) for f in files.values()]


def save_reverse(answers: dict) -> str:
    """Write the reverse stress test's answers (plain numbers, by
    shape) under data/ballast/stress/."""
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"reverse_{AS_OF}.json"
    f.write_text(json.dumps(answers, indent=1) + "\n")
    return str(f.relative_to(ROOT))


def load() -> dict:
    """The saved projections: years, products, paths and summary, and
    the reverse stress test's answers once they have been saved."""
    out = {"years": pd.read_csv(OUT / f"years_{AS_OF}.csv"),
           "products": pd.read_csv(OUT / f"products_{AS_OF}.csv"),
           "paths": pd.read_csv(OUT / f"paths_{AS_OF}.csv"),
           "summary": json.loads((OUT / f"summary_{AS_OF}.json")
                                 .read_text())}
    rev = OUT / f"reverse_{AS_OF}.json"
    if rev.exists():
        out["reverse"] = json.loads(rev.read_text())
    return out
