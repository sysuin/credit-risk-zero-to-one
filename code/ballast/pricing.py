"""Ballast v0.5: what a personal loan must charge, and what it returns.

A price has to pay for five things: the money lent (the funds
transfer price), the cost of running the loan, the losses expected
on loans like it, a return on the capital held against it, and a
margin. This module builds a price from those pieces and turns any
price back into the return it earns:

- `ftp_pct`: what Fernhill's treasury charges for funding a fixed-
  rate loan, from the swap curve at the loan's expected life;
- `fit_hazard`, `annual_rate`: default and prepayment rates per year
  from the book, as a smooth function of the score (provisional:
  Chapter 18 builds the PD, Chapter 19 the LGD);
- `expected_flows`: a loan's schedule followed month by month through
  default and prepayment, as expected amounts;
- `value`: what those flows earn after funding, running costs,
  expected losses and the charge for capital, discounted, with the
  risk-adjusted return on capital (RAROC);
- `floor_rate` and `waterfall`: the lowest rate that earns the
  hurdle, and what it is made of;
- `shift_take_up`, `best_rate`: how take-up moves with price, and
  the price that earns most within limits;
- `Grid`: Fernhill's price grid on Mark II-R's scale.

    from ballast import pricing
    p = pricing.load_pricing()
    pricing.price_application(p, score=571, amount_cents=1_200_000,
                              term_months=36)
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import brentq

from ballast import loanmath
from ballast.config import BALLAST

PRICING = BALLAST / "pricing"


# ------------------------------------------------- the assumptions

@dataclass(frozen=True)
class Costs:
    """Everything a price must cover besides funding and losses.

    Each number is an assumption until a later chapter measures it:
    the running cost is Chapters 2 and 11's; the capital held and
    the return required on it are Fernhill's finance team's working
    figures, which Chapter 21 replaces with what the rules require.
    """
    opex_pct: float = 2.5        # running cost, % of balance a year
    capital_pct: float = 10.0    # equity held, % of the balance
    hurdle_pct: float = 15.0     # return required on it, pre-tax
    lgd: float = 0.66            # share of a defaulted balance lost


def monthly_hazard(annual: float) -> float:
    """The monthly rate that compounds to `annual` over a year."""
    return 1 - (1 - annual) ** (1 / 12)


# ------------------------------------------------------- funding

def ftp_pct(market: dict, life_months: float) -> float:
    """The funds transfer price for a fixed-rate loan, % a year.

    Fernhill's treasury charges the swap rate for the loan's expected
    life, read off a curve through the policy rate (overnight), the
    two-year and the five-year swap, plus Fernhill's own funding
    spread over the policy rate (its cost of funds less the policy
    rate, which is negative when deposits are cheap).
    """
    tenors = [0.0, 24.0, 60.0]
    curve = [market["policy_rate_pct"], market["swap_2y_pct"],
             market["swap_5y_pct"]]
    swap = float(np.interp(life_months, tenors, curve))
    spread = market["cost_of_funds_pct"] - market["policy_rate_pct"]
    return swap + spread


# ------------------------------------------ rates from the book

@dataclass(frozen=True)
class Hazard:
    """A yearly rate that falls (or rises) smoothly with the score:
    the monthly rate is exp(a + b x score)."""
    a: float
    b: float
    se_b: float = 0.0

    def monthly(self, score) -> np.ndarray:
        s = np.asarray(score, dtype=float)
        return np.exp(self.a + self.b * s)

    def annual(self, score) -> np.ndarray:
        return 1 - (1 - self.monthly(score)) ** 12


def fit_hazard(score, events, months) -> Hazard:
    """Fit log(monthly rate) = a + b x score to counts of events in
    months at risk (a Poisson regression with the months as
    exposure). One row per loan, or per group of loans."""
    x = sm.add_constant(np.asarray(score, dtype=float))
    r = sm.GLM(np.asarray(events, dtype=float), x,
               family=sm.families.Poisson(),
               exposure=np.asarray(months, dtype=float)).fit()
    return Hazard(float(r.params[0]), float(r.params[1]),
                  float(r.bse[1]))


def annual_rate(events: float, months: float) -> float:
    """Events per month at risk, as a yearly rate."""
    return 1 - (1 - events / months) ** 12


# ------------------------------------------- the expected loan

def expected_flows(amount_cents: int, rate_pct: float,
                   term_months: int, annual_pd: float,
                   annual_prepay: float, lgd: float) -> pd.DataFrame:
    """A loan's schedule as expected amounts, month by month.

    Each month, of the loans still paying at its start, a share
    defaults (they pay nothing, and `lgd` of their balance is lost;
    the rest is recovered), a share of the others prepays (they pay
    the month's interest and the whole balance) and the remainder
    pay the scheduled instalment. Amounts are in cents, not rounded.
    """
    s = loanmath.schedule(amount_cents, rate_pct, term_months)
    hd = monthly_hazard(annual_pd)
    hp = monthly_hazard(annual_prepay)
    alive, rows = 1.0, []
    for t, b, i, p in zip(s["month"], s["opening"], s["interest"],
                          s["principal"]):
        dflt = alive * hd
        pre = (alive - dflt) * hp
        pay = alive - dflt - pre
        rows.append((t, alive * b, (pay + pre) * i, pay * p + pre * b,
                     dflt * b * (1 - lgd), dflt * b * lgd, alive))
        alive = pay
    return pd.DataFrame(rows, columns=["month", "balance", "interest",
                                       "principal", "recovered",
                                       "loss", "alive"])


def expected_life(flows: pd.DataFrame) -> float:
    """Average life in months: the expected balance summed over the
    months, divided by the amount lent."""
    return float(flows["balance"].sum() / flows["balance"].iloc[0])


@dataclass(frozen=True)
class Value:
    """What a loan earns, discounted at its funds transfer price.

    Money is in cents (present values); `*_pct` are the same amounts
    as a percentage of the average balance a year."""
    life_months: float
    ftp_pct: float
    balance_years: float       # discounted balance x years
    interest: float
    funding: float
    opex: float
    loss: float
    capital_charge: float
    profit: float              # before the charge for capital
    economic: float            # after it: zero at the hurdle
    raroc: float               # profit / capital, a year

    def pct(self, item: str) -> float:
        return getattr(self, item) / self.balance_years * 100


def value(amount_cents: int, rate_pct: float, term_months: int,
          annual_pd: float, annual_prepay: float, market: dict,
          costs: Costs = Costs()) -> Value:
    """The loan's expected earnings after every cost, and its RAROC.

    Capital is `capital_pct` of the balance. It earns the treasury
    rate (it is money the bank does not have to borrow), and
    shareholders want `hurdle_pct` on it, so the charge for it is
    capital x (hurdle - transfer price).
    """
    f = expected_flows(amount_cents, rate_pct, term_months,
                       annual_pd, annual_prepay, costs.lgd)
    life = expected_life(f)
    ftp = ftp_pct(market, life)
    disc = (1 + ftp / 1200) ** -f["month"].to_numpy(dtype=float)
    years = float((f["balance"] * disc).sum() / 12)
    interest = float((f["interest"] * disc).sum())
    loss = float((f["loss"] * disc).sum())
    funding = years * ftp / 100
    opex = years * costs.opex_pct / 100
    capital = years * costs.capital_pct / 100
    charge = capital * (costs.hurdle_pct - ftp) / 100
    profit = interest - funding - opex - loss + capital * ftp / 100
    economic = interest - funding - opex - loss - charge
    raroc = profit / capital if capital else float("nan")
    return Value(life, ftp, years, interest, funding, opex, loss,
                 charge, profit, economic, raroc)


def floor_rate(amount_cents: int, term_months: int, annual_pd: float,
               annual_prepay: float, market: dict,
               costs: Costs = Costs()) -> float:
    """The lowest rate at which the loan earns exactly the hurdle on
    its capital: everything covered, nothing to spare."""
    def gap(r):
        return value(amount_cents, r, term_months, annual_pd,
                     annual_prepay, market, costs).economic
    return float(brentq(gap, 0.0, 80.0, xtol=1e-6))


def waterfall(amount_cents: int, term_months: int, annual_pd: float,
              annual_prepay: float, market: dict,
              costs: Costs = Costs()) -> dict[str, float]:
    """The floor rate taken apart, in % of the balance a year.

    `expected_loss` is everything the floor needs beyond funding,
    running costs and capital: the losses themselves and the
    interest that defaulted loans never pay.
    """
    r = floor_rate(amount_cents, term_months, annual_pd,
                   annual_prepay, market, costs)
    v = value(amount_cents, r, term_months, annual_pd, annual_prepay,
              market, costs)
    out = {"funding": v.ftp_pct, "operating": costs.opex_pct,
           "capital": v.pct("capital_charge")}
    out["expected_loss"] = r - sum(out.values())
    out["floor"] = r
    return out


# ------------------------------------------------ price response

def logit(p):
    p = np.asarray(p, dtype=float)
    return np.log(p / (1 - p))


def shift_take_up(p0, slope: float, change_pct) -> np.ndarray:
    """Take-up after a price change, from take-up `p0` at today's
    price: the log odds of taking the loan move by `slope` for each
    point of price (`slope` is negative)."""
    z = logit(p0) + slope * np.asarray(change_pct, dtype=float)
    return 1 / (1 + np.exp(-z))


def fit_take_up(took, change_pct, controls: pd.DataFrame | None = None):
    """Logistic regression of take-up on the price change from
    policy (randomised in a price test) and any controls. Returns
    the statsmodels result; the slope is `params["change"]`."""
    x = pd.DataFrame({"change": np.asarray(change_pct, dtype=float)})
    if controls is not None:
        x = pd.concat([x, controls.reset_index(drop=True)], axis=1)
    x = sm.add_constant(x.astype(float), has_constant="add")
    return sm.Logit(np.asarray(took, dtype=float), x).fit(disp=0)


def best_rate(rates, p0: float, slope: float, base_rate: float,
              earns) -> tuple[float, pd.DataFrame]:
    """Of the candidate `rates`, the one that maximises expected
    earnings per approved applicant: take-up at that rate (shifted
    from `p0` at `base_rate`) times `earns(rate)`, what a loan booked
    at that rate earns after every cost."""
    rows = []
    for r in rates:
        up = float(shift_take_up(p0, slope, r - base_rate))
        e = float(earns(r))
        rows.append({"rate": r, "take_up": up, "per_loan": e,
                     "per_approval": up * e})
    t = pd.DataFrame(rows)
    return float(t.loc[t["per_approval"].idxmax(), "rate"]), t


# ---------------------------------------------------- the grid

@dataclass(frozen=True)
class Grid:
    """Prices by score band: `edges[k]` is the lowest score in tier
    k+1 (ascending), `rates` one per tier, lowest score first, set
    when the transfer price for a loan of `life_months` was
    `at_ftp_pct`. Prices move with funding: `pass_through` of every
    point that transfer price moves."""
    edges: tuple[int, ...]
    rates: tuple[float, ...]
    at_ftp_pct: float
    life_months: float = 16.0
    pass_through: float = 1.0

    def tier(self, score) -> np.ndarray:
        return np.searchsorted(np.asarray(self.edges),
                               np.asarray(score), side="right")

    def rate(self, score, ftp: float | None = None) -> np.ndarray:
        r = np.asarray(self.rates)[self.tier(score)]
        if ftp is not None:
            r = r + self.pass_through * (ftp - self.at_ftp_pct)
        return np.round(r, 2)

    def labels(self, low: int, high: int) -> list[str]:
        lo = [low, *self.edges]
        hi = [e - 1 for e in self.edges] + [high]
        return [f"{a}-{b}" for a, b in zip(lo, hi)]


def monotone(rates) -> list[float]:
    """Prices that never fall as risk rises: each riskier tier is at
    least as dear as the safer one above it (rates listed lowest
    score first)."""
    out = list(rates)
    for k in range(len(out) - 2, -1, -1):
        out[k] = max(out[k], out[k + 1])
    return out


# --------------------------------------------- saving and using it

@dataclass
class Pricing:
    """Everything Ballast prices with, saved together."""
    grid: Grid
    default: Hazard
    prepay: Hazard
    costs: Costs
    market: dict
    notes: dict = field(default_factory=dict)


def save_pricing(p: Pricing, path=None):
    path = path or PRICING / "pricing.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"grid": asdict(p.grid), "default": asdict(p.default),
            "prepay": asdict(p.prepay), "costs": asdict(p.costs),
            "market": p.market, "notes": p.notes}
    path.write_text(json.dumps(body, indent=1) + "\n")
    return path


def load_pricing(path=None) -> Pricing:
    path = path or PRICING / "pricing.json"
    d = json.loads(path.read_text())
    g = d["grid"]
    grid = Grid(tuple(g["edges"]), tuple(g["rates"]), g["at_ftp_pct"],
                g["life_months"], g["pass_through"])
    return Pricing(grid, Hazard(**d["default"]), Hazard(**d["prepay"]),
                   Costs(**d["costs"]), d["market"], d["notes"])


def price_application(p: Pricing, score: int, amount_cents: int,
                      term_months: int, market: dict | None = None,
                      costs: Costs | None = None) -> dict:
    """One approved application priced: its tier and rate on the
    grid, the floor rate for its risk, and the RAROC at the rate."""
    market = market or p.market
    costs = costs or p.costs
    pd_ = float(p.default.annual(score))
    pp = float(p.prepay.annual(score))
    rate = float(p.grid.rate(score,
                             ftp_pct(market, p.grid.life_months)))
    v = value(amount_cents, rate, term_months, pd_, pp, market, costs)
    return {"tier": int(p.grid.tier(score)) + 1, "rate": rate,
            "annual_pd": pd_, "annual_prepay": pp,
            "floor": floor_rate(amount_cents, term_months, pd_, pp,
                                market, costs),
            "raroc": v.raroc, "economic_cents": v.economic,
            "ftp": v.ftp_pct, "life_months": v.life_months}


def with_costs(costs: Costs, **change) -> Costs:
    """A copy of the assumptions with some of them changed."""
    return replace(costs, **change)
