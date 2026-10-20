"""Moving risk off the balance sheet.

Chapter 28's module. Most of it is a securitisation of Fernhill's
car loans, built from the ground up:

- **the pool**: the car loans Fernhill could sell on the cut-off
  date, each with its own amortisation schedule, score band and car;
- **the assumptions**: Chapter 18's default hazards, a prepayment
  curve measured from Fernhill's history, and Chapter 19's line from
  loan-to-value to loss given default, with the used-car index of
  each published scenario;
- **the projection**: the pool's expected cash flows month by month
  (interest, scheduled principal, prepayments, defaults, recoveries);
- **the waterfall**: how a special-purpose vehicle pays those cash
  flows out to its notes, senior first, with excess spread trapped
  to cover losses before anything reaches the equity;
- **a Monte Carlo** of the pool with correlated defaults, each draw
  run through the same waterfall, for each tranche's loss
  distribution.

Two short parts cover the other ways a lender moves credit risk:
what a credit default swap on a client costs, and the exposure a
lender takes on when it sells a client an interest-rate swap
(expected exposure, potential future exposure and a simple CVA).

    import fernhill
    from ballast import securitisation as sec
    con = fernhill.connect()
    deal = sec.inputs(con)                    # pool and assumptions
    cf = sec.project(deal, "base")            # expected cash flows
    w = sec.waterfall(cf, sec.notes(deal))    # who is paid what

Capital figures here are illustrations on one stated rule
(`CAPITAL_PCT`); Chapter 21 computes capital properly. This module
never reads the truth database.
"""
from __future__ import annotations

from dataclasses import dataclass

import json

import numpy as np
import pandas as pd
from scipy.stats import norm

from ballast import performance as perf
from ballast.config import AS_OF, BALLAST, ROOT
from ballast.market import hazard_from_spread
from ballast.parameters import lgd as lgdm
from ballast.parameters import pd as pdm

PRODUCT = "auto"
CUT_OFF = AS_OF                 # the pool as it stood on this date
RECOVERY_LAG = 3                # months from default to the car's sale
SERVICING_PCT = 1.00            # % a year on the pool, to the servicer
PREPAY_BAND = 6                 # months of age per prepayment band
OUT = BALLAST / "securitisation"


@dataclass(frozen=True)
class Tranche:
    """One class of note: its share of the pool at closing and its
    margin over the two-year swap rate (None for the equity, which
    has no coupon and is paid whatever is left)."""
    name: str
    share: float
    margin_pct: float | None


# The arranger's proposal: sequential pay, senior first.
STRUCTURE = (Tranche("A", 0.93, 0.60),
             Tranche("B", 0.05, 2.50),
             Tranche("C", 0.02, None))
RETAIN_VERTICAL = 0.05          # Fernhill keeps this share of each
CAPITAL_PCT = 10.0              # illustrative capital on a car loan, %
HURDLE_PCT = 15.0               # return Fernhill asks of its capital, %


# --------------------------------------------------------- the pool

def candidates(con, cut_off=CUT_OFF) -> pd.DataFrame:
    """Every car loan open on the cut-off date, with the flags that
    decide whether it may go into the pool."""
    rows = con.execute("""
        WITH h AS (
            SELECT account_id, count(*) - 1 AS mob,
                   max(missed) AS worst
            FROM performance
            WHERE product = ? AND month <= ?
            GROUP BY 1)
        SELECT p.account_id, a.open_date, p.balance_cents,
               p.status, p.missed, a.rate_pct, a.payment_cents,
               a.term_months, a.collateral_value_cents, h.mob,
               h.worst, ap.mark1_score
        FROM performance p
        JOIN accounts a USING (account_id)
        JOIN h USING (account_id)
        LEFT JOIN applications ap USING (app_id)
        WHERE p.product = ? AND p.month = ?
          AND p.status IN ('up_to_date', 'arrears', 'default')
        ORDER BY p.account_id""",
                       [PRODUCT, cut_off, PRODUCT, cut_off]).df()
    eps = perf.default_episodes(con, "dod2021", products=[PRODUCT])
    ever = set(eps.loc[pd.to_datetime(eps["default_month"])
                       <= pd.Timestamp(cut_off), "account_id"])
    rows["up_to_date"] = rows["status"] == "up_to_date"
    rows["seasoned"] = rows["mob"] >= 1
    rows["never_defaulted"] = ~rows["account_id"].isin(ever)
    rows["eligible"] = (rows.up_to_date & rows.seasoned
                        & rows.never_defaulted
                        & (rows.balance_cents > 0))
    return rows


def remaining_payments(balance, rate_pct, payment) -> np.ndarray:
    """Payments left on a level-payment loan, from its balance."""
    b = np.asarray(balance, dtype=float)
    r = np.asarray(rate_pct, dtype=float) / 1200
    p = np.asarray(payment, dtype=float)
    n = -np.log(1 - r * b / p) / np.log(1 + r)
    return np.ceil(n - 1e-9).astype(int)


def pool(con, cut_off=CUT_OFF) -> pd.DataFrame:
    """The eligible loans, with remaining term, band and the car's
    value indexed to the cut-off date."""
    c = candidates(con, cut_off)
    p = c[c["eligible"]].reset_index(drop=True)
    p["remaining"] = remaining_payments(p.balance_cents, p.rate_pct,
                                        p.payment_cents)
    p["band"] = pdm.band(p["mark1_score"],
                         pdm.SCORE_EDGES[PRODUCT])
    idx = _car_index(con)
    opened = (pd.to_datetime(p["open_date"])
              + pd.offsets.MonthEnd(0)).map(idx)
    p["index_open"] = opened.to_numpy()
    p["ltv"] = p["balance_cents"] / (
        p["collateral_value_cents"] * idx[pd.Timestamp(cut_off)]
        / p["index_open"])
    return p


def _car_index(con) -> pd.Series:
    m = con.execute("SELECT month, used_car_index FROM macro "
                    "ORDER BY month").df()
    return pd.Series(m.used_car_index.to_numpy(),
                     index=pd.to_datetime(m.month))


def schedules(p: pd.DataFrame, months: int | None = None):
    """Each loan's contractual balance after 0, 1, 2 ... payments,
    with no default and no prepayment: an (n, T + 1) array."""
    months = months or int(p["remaining"].max())
    b = p["balance_cents"].to_numpy(dtype=float)
    r = p["rate_pct"].to_numpy() / 1200
    pay = p["payment_cents"].to_numpy(dtype=float)
    out = np.zeros((len(p), months + 1))
    out[:, 0] = b
    for t in range(1, months + 1):
        b = np.maximum(b * (1 + r) - pay, 0.0)
        b[b < 1] = 0.0                     # the last payment clears it
        out[:, t] = b
    return out


# -------------------------------------------------- the assumptions

def prepayment_curve(con, until=CUT_OFF) -> pd.DataFrame:
    """Monthly prepayment rate (SMM) of car loans by age, from every
    month a loan was open, not in default and could have prepaid."""
    d = con.execute("""
        WITH p AS (
            SELECT month, status,
                   row_number() OVER w - 1 AS mob,
                   lag(status) OVER w AS prev,
                   lag(missed) OVER w AS prev_missed
            FROM performance WHERE product = ?
            WINDOW w AS (PARTITION BY account_id ORDER BY month))
        SELECT mob, count(*) AS at_risk,
               count(*) FILTER (WHERE status = 'prepaid') AS prepaid
        FROM p
        WHERE prev IN ('up_to_date', 'arrears') AND prev_missed < 3
          AND month <= ?
        GROUP BY 1 ORDER BY 1""", [PRODUCT, until]).df()
    d["band"] = (d["mob"] - 1) // PREPAY_BAND * PREPAY_BAND + 1
    g = d.groupby("band")[["at_risk", "prepaid"]].sum()
    g = g[g["at_risk"] >= 1000]            # too few months beyond
    g["smm"] = g["prepaid"] / g["at_risk"]
    g["cpr"] = 1 - (1 - g["smm"]) ** 12
    return g


def smm_at(curve: pd.DataFrame, mob) -> np.ndarray:
    """The prepayment rate for loans of the given ages; ages past the
    curve's last band keep its last rate."""
    mob = np.asarray(mob)
    bands = curve.index.to_numpy()
    i = np.clip(np.searchsorted(bands, mob, side="right") - 1, 0,
                len(bands) - 1)
    return curve["smm"].to_numpy()[i]


def car_lgd_line(con) -> tuple[float, float]:
    """Chapter 19's line from indexed loan-to-value at default to the
    LGD of a car workout (cures count as zero), refitted here."""
    w = lgdm.workouts(con)
    w = w[w["product"] == PRODUCT]
    f = lgdm.cash_flows(con, w)
    w = lgdm.realised(w, f, lgdm.discount_rates(con, w))
    w = w[(w["outcome"] != "open") & w["lgd"].notna()]
    idx = _car_index(con)
    opened = pd.to_datetime(w["open_date"]) + pd.offsets.MonthEnd(0)
    value = w["collateral_cents"] * (w["default_month"].map(idx)
                                     / opened.map(idx)).to_numpy()
    slope, icept = np.polyfit(w["ead_cents"] / value, w["lgd"], 1)
    return float(icept), float(slope)


@dataclass
class Deal:
    """The pool and every assumption the projection needs."""
    loans: pd.DataFrame
    sched: np.ndarray
    hazard: pdm.HazardModel
    prepay: pd.DataFrame
    lgd_line: tuple[float, float]
    cure_rate: float
    swap_2y_pct: float
    cost_of_funds_pct: float
    paths: dict


def inputs(con, cut_off=CUT_OFF) -> Deal:
    """Everything the deal is projected from, as at the cut-off."""
    p = pool(con, cut_off)
    rates = con.execute("SELECT swap_2y_pct, cost_of_funds_pct FROM "
                        "market_rates WHERE month = ?",
                        [cut_off]).fetchone()
    car = _car_index(con)
    paths = {}
    for s in ("base", "downside", "severe"):
        sc = con.execute("""SELECT month, unemployment_pct,
                                   used_car_index FROM scenarios
                            WHERE as_of = ? AND scenario = ?
                            ORDER BY month""", [cut_off, s]).df()
        paths[s] = (sc.unemployment_pct.to_numpy(),
                    sc.used_car_index.to_numpy())
    lr = pdm.long_run_unemployment(con)
    paths["long_run"] = (np.full(60, lr),
                         np.full(60, car[pd.Timestamp(cut_off)]))
    auto = lgdm.load()["products"][PRODUCT]
    return Deal(p, schedules(p), pdm.load_hazards()[PRODUCT],
                prepayment_curve(con, cut_off), car_lgd_line(con),
                float(auto["cure_rate"]), float(rates[0]),
                float(rates[1]), paths)


def _extend(x: np.ndarray, months: int) -> np.ndarray:
    """A scenario path, held at its last value beyond 2030."""
    return np.r_[x, np.full(max(months - len(x), 0), x[-1])][:months]


def loan_matrices(deal: Deal, scenario: str, hazard_scale=1.0):
    """Month-by-month arrays for every loan (n x T): the monthly
    default hazard, the prepayment rate, and the LGD if it defaulted
    that month, under one scenario's unemployment and car prices."""
    p, B = deal.loans, deal.sched
    n, T = B.shape[0], B.shape[1] - 1
    u, car = (_extend(a, T) for a in deal.paths[scenario])
    mob = p["mob"].to_numpy()[:, None] + np.arange(1, T + 1)[None, :]
    bands = np.repeat(p["band"].to_numpy(), T)
    h = deal.hazard.hazard(mob.ravel(), bands,
                           np.tile(u, n)).reshape(n, T)
    h = np.minimum(h * hazard_scale, 1.0)
    alive = B[:, :-1] > 0
    h = np.where(alive, h, 0.0)
    q = np.where(alive, smm_at(deal.prepay, mob), 0.0)
    value = (p["collateral_value_cents"].to_numpy()[:, None]
             * car[None, :] / p["index_open"].to_numpy()[:, None])
    a, b = deal.lgd_line
    lgd = np.clip(a + b * B[:, :-1] / value, 0.0, 1.0)
    return h, q, lgd


# --------------------------------------------------- the projection

FLOWS = ["balance", "interest", "scheduled", "prepaid", "defaulted",
         "recovered"]


def project(deal: Deal, scenario: str = "base", hazard_scale=1.0,
            prepay_scale=1.0) -> pd.DataFrame:
    """The pool's expected cash flows, month by month, in cents.

    In each month a surviving share of each loan first defaults at
    its hazard (owing its whole balance, recovered `RECOVERY_LAG`
    months later less its LGD); of what does not default, a share
    prepays its balance and the rest pays its scheduled instalment.
    `balance` is the pool at the start of the month.
    """
    h, q, lgd = loan_matrices(deal, scenario, hazard_scale)
    q = np.minimum(q * prepay_scale, 1.0)
    B = deal.sched
    r = deal.loans["rate_pct"].to_numpy()[:, None] / 1200
    n, T = h.shape
    surv = np.cumprod(np.c_[np.ones(n), (1 - h) * (1 - q)], axis=1)
    s0, b0, b1 = surv[:, :-1], B[:, :-1], B[:, 1:]
    stay = s0 * (1 - h)
    defaulted = s0 * h * b0
    out = pd.DataFrame({
        "balance": (s0 * b0).sum(0),
        "interest": (stay * r * b0).sum(0),
        "scheduled": (stay * (b0 - b1)).sum(0),
        "prepaid": (stay * q * b1).sum(0),
        "defaulted": defaulted.sum(0),
        "recovered": np.zeros(T)})
    out = out.reindex(range(T + RECOVERY_LAG), fill_value=0.0)
    rec = (defaulted * (1 - lgd)).sum(0)
    out.loc[RECOVERY_LAG:RECOVERY_LAG + T - 1, "recovered"] = rec
    out.index = out.index + 1
    out.index.name = "month"
    return out


def lifetime_pd(deal: Deal, scenario: str = "long_run"):
    """Each loan's chance of defaulting before its last payment if it
    could not prepay (the net hazard: prepayment is allowed for by
    shrinking the exposure instead), and the month it would."""
    h, q, _ = loan_matrices(deal, scenario)
    undefaulted = np.cumprod(np.c_[np.ones(len(h)), 1 - h], axis=1)
    marginal = undefaulted[:, :-1] * h
    return marginal.sum(1), marginal.cumsum(1)


# ------------------------------------------------------ the waterfall

def coupons(deal: Deal, structure=STRUCTURE) -> dict:
    """Each note's coupon, % a year: the two-year swap rate on the
    cut-off date plus its margin; None for the equity."""
    return {t.name: (None if t.margin_pct is None
                     else deal.swap_2y_pct + t.margin_pct)
            for t in structure}


def notes(deal: Deal, structure=STRUCTURE) -> list[tuple]:
    """(name, size in cents, coupon % or None), senior first."""
    total = float(deal.loans["balance_cents"].sum())
    c = coupons(deal, structure)
    return [(t.name, t.share * total, c[t.name]) for t in structure]


def waterfall(cf, tranches, servicing_pct=SERVICING_PCT) -> dict:
    """Pay the pool's cash out to the notes, month by month.

    `cf` holds arrays (or DataFrame columns) of `FLOWS`, each of shape
    (..., T): one deal, or many simulated ones along the leading axis.

    Revenue (interest and recoveries) pays, in order: the servicer;
    each coupon note's interest, senior first; then the **principal
    deficiency ledger** (PDL), the defaulted principal not yet made
    good, so that excess spread replaces lost principal before
    anything else; whatever is left is released to the equity.
    Principal (scheduled, prepaid, and what revenue moved across for
    the PDL) repays the notes in order of seniority. When the pool has
    paid its last, a note still outstanding has lost what it is owed.
    """
    get = (lambda k: np.asarray(cf[k], dtype=float))  # noqa: E731
    bal_pool = get("balance")
    T = bal_pool.shape[-1]
    lead = bal_pool.shape[:-1]
    names = [t[0] for t in tranches]
    bal = {n: np.full(lead, float(s)) for n, s, _ in tranches}
    zero = (lambda: np.zeros(lead + (T,)))  # noqa: E731
    paid_int = {n: zero() for n in names}
    paid_prin = {n: zero() for n in names}
    short = {n: zero() for n in names}
    fee, credit, residual, pdl = zero(), zero(), zero(), zero()
    owed = np.zeros(lead)
    for m in range(T):
        rev = get("interest")[..., m] + get("recovered")[..., m]
        fee[..., m] = np.minimum(rev, bal_pool[..., m]
                                 * servicing_pct / 1200)
        rev = rev - fee[..., m]
        for n, _, c in tranches:
            if c is None:
                continue
            due = bal[n] * c / 1200
            pay = np.minimum(rev, due)
            paid_int[n][..., m], short[n][..., m] = pay, due - pay
            rev = rev - pay
        owed = owed + get("defaulted")[..., m]
        cr = np.minimum(rev, owed)
        owed, rev = owed - cr, rev - cr
        credit[..., m], pdl[..., m] = cr, owed
        prin = get("scheduled")[..., m] + get("prepaid")[..., m] + cr
        for n in names:
            pay = np.minimum(prin, bal[n])
            paid_prin[n][..., m] = pay
            bal[n], prin = bal[n] - pay, prin - pay
        residual[..., m] = rev + prin
    return {"names": names, "size": {n: s for n, s, _ in tranches},
            "interest": paid_int, "principal": paid_prin,
            "shortfall": short, "loss": bal, "fee": fee,
            "pdl_credit": credit, "pdl": pdl, "residual": residual}


def tranche_table(w: dict) -> pd.DataFrame:
    """One row per note: what it was paid, what it lost, and its
    weighted average life in years (for a single deal)."""
    rows = []
    for n in w["names"]:
        prin = w["principal"][n]
        months = np.arange(1, prin.shape[-1] + 1)
        wal = (prin * months).sum(-1) / max(prin.sum(-1), 1e-9) / 12
        rows.append({"note": n, "size": w["size"][n],
                     "interest": w["interest"][n].sum(-1),
                     "principal": prin.sum(-1), "loss": w["loss"][n],
                     "loss_pct": w["loss"][n] / w["size"][n],
                     "wal": wal})
    return pd.DataFrame(rows).set_index("note")


def attachment(structure=STRUCTURE) -> dict:
    """Each tranche's attachment and detachment point, as a share of
    the pool: the losses at which it starts and finishes losing."""
    out, top = {}, 1.0
    for t in structure:
        out[t.name] = (max(0.0, round(top - t.share, 10)), top)
        top = round(top - t.share, 10)
    return out


def tranche_loss(pool_loss, attach: float, detach: float):
    """A tranche's loss, as a share of its size, when the pool loses
    `pool_loss` of its balance and nothing else absorbs it."""
    x = np.asarray(pool_loss, dtype=float)
    return np.clip(x - attach, 0.0, detach - attach) / (detach - attach)


# ----------------------------------------------------- Monte Carlo

def vasicek_pd(pd_, rho: float, z) -> np.ndarray:
    """Chapter 1's conditional PD: the chance of default given the
    shared economy z (negative z is a bad economy)."""
    pd_ = np.clip(np.asarray(pd_, dtype=float), 1e-12, 1 - 1e-12)
    return norm.cdf((norm.ppf(pd_) - np.sqrt(rho) * z)
                    / np.sqrt(1 - rho))


def simulate(deal: Deal, n_sims: int, rho: float, seed: int,
             scenario: str = "long_run") -> dict:
    """Simulated cash flows for the pool, one deal per row.

    Each draw takes one value of the shared economy for the life of
    the deal. Every loan defaults or not at its lifetime PD moved by
    that value (one-factor Vasicek), in a month drawn from its own
    default timing; its exposure then is its balance with expected
    prepayments taken off. A defaulted loan cures at the product's
    cure rate (no loss) or loses its collateral-driven LGD scaled up
    so that the average, cures included, is the line's.
    """
    rng = np.random.default_rng(seed)
    h, q, lgd = loan_matrices(deal, scenario)
    B = deal.sched
    n, T = h.shape
    r = deal.loans["rate_pct"].to_numpy()[:, None] / 1200
    Q = np.cumprod(np.c_[np.ones(n), 1 - q], axis=1)[:, :-1]
    b0, b1 = B[:, :-1], B[:, 1:]
    X = {"interest": Q * r * b0, "scheduled": Q * (b0 - b1),
         "prepaid": Q * q * b1, "balance": Q * b0}
    ead = Q * b0
    undef = np.cumprod(np.c_[np.ones(n), 1 - h], axis=1)
    cum = (undef[:, :-1] * h).cumsum(1)
    life = cum[:, -1]
    timing = cum / np.maximum(life, 1e-15)[:, None]
    z = rng.standard_normal(n_sims)
    c = deal.cure_rate
    base = {k: v.sum(0) for k, v in X.items()}
    L = T + RECOVERY_LAG
    cf = {k: np.zeros((n_sims, L)) for k in FLOWS}
    for k in ("interest", "scheduled", "prepaid", "balance"):
        cf[k][:, :T] = base[k]
    months = np.arange(T)
    for s in range(n_sims):
        p = vasicek_pd(life, rho, z[s])
        d = np.flatnonzero(rng.random(n) < p)
        if not len(d):
            continue
        tau = (timing[d] < rng.random(len(d))[:, None]).sum(1)
        tau = np.minimum(tau, T - 1)
        after = months[None, :] >= tau[:, None]
        for k in ("interest", "scheduled", "prepaid"):
            cf[k][s, :T] -= (X[k][d] * after).sum(0)
        gone = months[None, :] > tau[:, None]
        cf["balance"][s, :T] -= (X["balance"][d] * gone).sum(0)
        e = ead[d, tau]
        cured = rng.random(len(d)) < c
        loss = np.where(cured, 0.0,
                        np.minimum(lgd[d, tau] / (1 - c), 1.0))
        np.add.at(cf["defaulted"][s], tau, e)
        np.add.at(cf["recovered"][s], tau + RECOVERY_LAG,
                  e * (1 - loss))
    for k in ("interest", "scheduled", "prepaid", "balance"):
        cf[k] = np.maximum(cf[k], 0.0)
    cf["z"] = z
    return cf


def breakeven(deal: Deal, tranche: str, scenario: str = "severe",
              structure=STRUCTURE, top: float = 64.0) -> float:
    """The multiple of a scenario's default hazards at which a
    tranche first loses a dollar, by bisection."""
    def loses(k):
        w = waterfall(project(deal, scenario, hazard_scale=k),
                      notes(deal, structure))
        return w["loss"][tranche] > 100
    lo, hi = 1.0, top
    if loses(lo):
        return lo
    if not loses(hi):
        return float("inf")
    while hi - lo > 0.05:
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if loses(mid) else (mid, hi)
    return hi


def pool_loss(cf, total: float) -> np.ndarray:
    """Defaulted principal less recoveries, as a share of the pool at
    closing."""
    d = np.asarray(cf["defaulted"]).sum(-1)
    r = np.asarray(cf["recovered"]).sum(-1)
    return (d - r) / total


# ------------------------------------------------ capital, simplified

def illustrative_capital(retained: dict, structure=STRUCTURE,
                         capital_pct=CAPITAL_PCT) -> float:
    """Capital Fernhill holds after a sale, as a share of the pool,
    on one stated rule: the pool needs `capital_pct` of capital, which
    is its first `capital_pct` of losses; whoever bears a slice of
    those losses holds that slice of capital, dollar for dollar.

    `retained` maps a tranche name to the share of it Fernhill keeps.
    Real rules add floors and formulas this leaves out (Chapter 21).
    """
    k = capital_pct / 100
    out = 0.0
    for name, (a, d) in attachment(structure).items():
        inside = max(0.0, min(d, k) - a)
        out += retained.get(name, 0.0) * inside
    return out


# ------------------------------------ credit protection on one client

def cds_cost(notional_cents: float, spread_bps: float,
             years: float = 5.0, lgd: float = 0.60) -> dict:
    """What buying protection costs and what it implies: the premium
    a year, and the market's default intensity and one-year PD from
    the credit triangle (Chapter 17)."""
    lam = float(hazard_from_spread(spread_bps, lgd))
    return {"premium_a_year": notional_cents * spread_bps / 1e4,
            "premium_total": notional_cents * spread_bps / 1e4 * years,
            "hazard": lam, "pd_1y": 1 - np.exp(-lam),
            "payout_if_default": notional_cents * lgd}


# --------------------------------- counterparty exposure on a swap

def swap_rate_paths(start_pct: float, vol_pct: float, months: int,
                    n_paths: int, seed: int) -> np.ndarray:
    """Monthly paths of the swap rate, in %, as a random walk with
    normal steps (a deliberately plain model: no drift, no mean
    reversion, one rate for the whole curve)."""
    rng = np.random.default_rng(seed)
    steps = (rng.standard_normal((n_paths, months)) * vol_pct
             / np.sqrt(12))
    return start_pct + np.c_[np.zeros(n_paths), steps.cumsum(1)]


def swap_values(paths_pct: np.ndarray, fixed_pct: float, years: int,
                notional: float, receive_fixed: bool = True):
    """Mark-to-market of a swap with quarterly payments at each month
    on the paths: (fixed - market) x annuity x notional for the side
    that receives fixed, on a flat curve at the simulated rate."""
    months = paths_pct.shape[1] - 1
    out = np.zeros_like(paths_pct)
    pay_months = np.arange(3, years * 12 + 1, 3)
    for t in range(months + 1):
        left = pay_months[pay_months > t]
        if not len(left):
            continue
        s = paths_pct[:, t] / 100
        tau = (left - t) / 12
        annuity = (0.25 * (1 + s[:, None] / 4) ** (-4 * tau[None, :])
                   ).sum(1)
        out[:, t] = (fixed_pct / 100 - s) * annuity * notional
    return out if receive_fixed else -out


def exposure_profile(values: np.ndarray, pfe_q: float = 0.95):
    """Expected exposure and potential future exposure at each month:
    the mean and a high quantile of what the counterparty would owe."""
    e = np.maximum(values, 0.0)
    return e.mean(0), np.quantile(e, pfe_q, axis=0)


def cva(ee: np.ndarray, spread_bps: float, discount_pct: float,
        lgd: float = 0.60) -> float:
    """Credit valuation adjustment: expected exposure, times the
    chance the counterparty defaults in each month (from its CDS
    spread), times the share lost, discounted, summed."""
    lam = float(hazard_from_spread(spread_bps, lgd))
    t = np.arange(len(ee)) / 12
    survive = np.exp(-lam * t)
    dpd = np.r_[0.0, survive[:-1] - survive[1:]]
    df = np.exp(-discount_pct / 100 * t)
    return float(lgd * (ee * dpd * df).sum())


# ------------------------------------------------------------ saving

def summary(deal: Deal, scenarios=("base", "downside", "severe")
            ) -> dict:
    """The deal in one dictionary: the pool, the structure, and each
    scenario's pool loss, excess spread and losses by class."""
    total = float(deal.loans["balance_cents"].sum())
    out = {"cut_off": str(CUT_OFF), "loans": int(len(deal.loans)),
           "pool_cents": int(total),
           "structure": {t.name: {"share": t.share,
                                  "attach_detach": attachment()[t.name],
                                  "coupon_pct": coupons(deal)[t.name]}
                         for t in STRUCTURE},
           "scenarios": {}}
    for s in scenarios:
        cf = project(deal, s)
        w = waterfall(cf, notes(deal))
        out["scenarios"][s] = {
            "defaults_pct": float(cf.defaulted.sum() / total),
            "net_loss_pct": float((cf.defaulted - cf.recovered).sum()
                                  / total),
            "released_cents": int(round(w["residual"].sum())),
            "loss_cents": {n: int(round(float(w["loss"][n])))
                           for n in w["names"]}}
    return out


def save(obj: dict, name: str = "deal.json") -> str:
    """Write under data/ballast/securitisation/."""
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(obj, indent=1) + "\n")
    return str(path.relative_to(ROOT))
