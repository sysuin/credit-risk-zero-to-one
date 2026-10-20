"""Structuring a commercial facility: what Fernhill lends, on what
terms, and what must stay true while the money is out.

A spread (Chapter 14) says what a company is. A structure fits a
facility to it. The module:

- sizes a working-capital revolver from the spread;
- computes a borrowing base on receivables and inventory, with the
  advance rates and ineligibles written down as assumptions;
- sets financial covenants from the company's own numbers, with the
  headroom stated, and tests accounts against them;
- limits what the owners may take out while the facility is drawn;
- adds up what a facility earns, and puts the terms in a term sheet.

    import fernhill
    from ballast.commercial import spreading as sp, structure as st
    con = fernhill.connect()
    m = sp.company_id(con, "Meridian Supply Co.")
    s = sp.spread(sp.accounts(con, m))
    need = st.revolver_need(s, 2025, growth=0.137)
    bb = st.borrowing_base(s.loc["receivables", 2025],
                           s.loc["inventory", 2025])

Money stays in integer cents; ratios and rates are floats.
"""
from __future__ import annotations

import math
import textwrap
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Assumptions. Fernhill has never lent against a borrowing base
# (Chapter 3), so none of these comes from its own experience; each
# is a term to negotiate and a question for the borrower.
ADVANCE_RECEIVABLES = 0.80     # lent against each eligible $1 owed
ADVANCE_INVENTORY = 0.50       # lent against each eligible $1 of stock
INELIGIBLE_RECEIVABLES = 0.15  # share, until the aged listing arrives
INELIGIBLE_INVENTORY = 0.20    # slow-moving, in transit, on consignment
HEADROOM = 0.30                # EBITDA may fall 30% before a breach
STEP = 0.25                    # covenants are set in quarter-turns
SWING = 0.10                   # in-year working capital above year end
PAYOUT_CAP = 0.35              # of last year's net income, while drawn
DIVIDEND_MAX_LEVERAGE = 2.50   # no distribution above this leverage
COMMITMENT_SHARE = 0.35        # undrawn fee, as a share of the margin
ARRANGEMENT_PCT = 0.005        # of the limit, once, at signing


# ------------------------------------------------------ sizing

def working_capital(s: pd.DataFrame, year: int) -> int:
    """Receivables plus inventory less trade payables, in cents."""
    c = s[year]
    return int(c.receivables + c.inventory - c.payables)


def revolver_need(s: pd.DataFrame, year: int, growth: float,
                  years: int = 2, swing: float = SWING,
                  refinance: int | None = None) -> pd.Series:
    """What a working-capital revolver must carry, in cents.

    Three parts: the short-term borrowing it replaces (by default
    the spread's borrowings due within a year); the growth in
    working capital over `years` if sales grow at `growth` a year
    and the working-capital days stay where they were in `year`;
    and an allowance for the swing inside a year, as a share of the
    working capital at the end of the horizon, because year-end
    balances are one day's photograph. The limit is the total
    rounded up to the next whole million dollars.
    """
    wc = working_capital(s, year)
    if refinance is None:
        refinance = int(s.loc["short_term_debt", year])
    future = wc * (1 + growth) ** years
    parts = {
        "refinance": int(refinance),
        "growth": int(round(future - wc)),
        "swing": int(round(future * swing)),
    }
    total = sum(parts.values())
    parts["total"] = total
    parts["limit"] = int(math.ceil(total / 100_000_000) * 100_000_000)
    return pd.Series(parts, dtype="int64")


def pro_forma(s: pd.DataFrame, year: int, add: int, keep: int,
              rate_new: float) -> pd.Series:
    """Leverage and cover with a new facility drawn in full.

    `keep` is the existing debt that stays (cents), charged at the
    year's implied rate (interest over borrowings); `add` is the new
    facility, charged at `rate_new`. EBITDA is the year's.
    """
    c = s[year]
    old_rate = c.interest / c.total_debt if c.total_debt else 0.0
    debt = keep + add
    interest = keep * old_rate + add * rate_new
    return pd.Series({
        "debt": debt, "interest": interest, "ebitda": c.ebitda,
        "leverage": debt / c.ebitda if c.ebitda > 0 else np.inf,
        "cover": c.ebitda / interest if interest else np.inf})


# ---------------------------------------------- the borrowing base

def ineligible_receivables(ledger: pd.DataFrame, max_days: int = 90,
                           cross_age: float = 0.5,
                           concentration: float = 0.25
                           ) -> pd.DataFrame:
    """Apply the usual eligibility rules to an aged receivables ledger.

    `ledger` has one row per customer: `customer`, `balance` (cents),
    `over_days` (cents outstanding longer than `max_days` from the
    invoice date) and `flag` (None, or a reason the whole balance is
    out: "disputed", "related", "foreign", ...). In order:

    1. a flagged customer's whole balance is ineligible;
    2. a customer with more than `cross_age` of its balance overdue
       is ineligible in full ("cross-ageing": the rest is unlikely
       to be paid on time either);
    3. otherwise the overdue part is ineligible;
    4. what is still eligible for one customer above `concentration`
       of the whole ledger is ineligible, so one customer cannot
       carry the facility.
    """
    d = ledger.copy()
    total = int(d.balance.sum())
    cap = int(concentration * total)
    rows = []
    for bal, over, flag in zip(d.balance, d.over_days, d.flag):
        if flag is not None and flag == flag:
            out, why = bal, str(flag)
        elif over > cross_age * bal:
            out, why = bal, "cross-aged"
        else:
            out, why = over, "overdue" if over > 0 else ""
        excess = max(bal - out - cap, 0)
        if excess:
            why = f"{why}, concentration" if why else "concentration"
        rows.append((int(out + excess), why))
    d["ineligible"] = pd.Series([r[0] for r in rows], index=d.index,
                                dtype="int64")
    d["eligible"] = (d.balance - d.ineligible).astype("int64")
    d["reason"] = [r[1] for r in rows]
    return d


def borrowing_base(receivables: int, inventory: int,
                   ineligible_receivables: int | None = None,
                   ineligible_inventory: int | None = None,
                   advance_receivables: float = ADVANCE_RECEIVABLES,
                   advance_inventory: float = ADVANCE_INVENTORY,
                   reserves: int = 0) -> pd.Series:
    """How much may be drawn against receivables and inventory.

    Ineligibles default to the module's assumed shares; pass the
    amounts from an aged listing and a stock report when they exist.
    Advances are rounded down to the cent. `reserves` is any amount
    the lender holds back (rent or tax that would rank ahead of it,
    a dilution reserve).
    """
    receivables, inventory = int(receivables), int(inventory)
    if ineligible_receivables is None:
        ineligible_receivables = round(receivables
                                       * INELIGIBLE_RECEIVABLES)
    if ineligible_inventory is None:
        ineligible_inventory = round(inventory * INELIGIBLE_INVENTORY)
    er = receivables - int(ineligible_receivables)
    ei = inventory - int(ineligible_inventory)
    ar = math.floor(er * advance_receivables)
    ai = math.floor(ei * advance_inventory)
    return pd.Series({
        "receivables": receivables,
        "ineligible_receivables": -int(ineligible_receivables),
        "eligible_receivables": er,
        "receivables_advance": ar,
        "inventory": inventory,
        "ineligible_inventory": -int(ineligible_inventory),
        "eligible_inventory": ei,
        "inventory_advance": ai,
        "reserves": -int(reserves),
        "base": max(ar + ai - int(reserves), 0),
    }, dtype="int64")


def availability(base: int, limit: int, drawn: int) -> int:
    """What may still be drawn: the lesser of limit and base, less
    what is drawn, never below zero."""
    return max(min(int(base), int(limit)) - int(drawn), 0)


# ------------------------------------------------------ covenants

def _step(x: float, step: float = STEP) -> float:
    """x rounded to the nearest `step`."""
    return round(round(x / step) * step, 2)


def covenant_levels(leverage: float, cover: float,
                    headroom: float = HEADROOM,
                    step: float = STEP) -> tuple[float, float]:
    """A maximum leverage and minimum cover with `headroom` in them.

    Both are set so that EBITDA could fall by about `headroom` from
    the case they are set on before either is breached: leverage
    over (1 - headroom), cover times (1 - headroom), each rounded to
    the nearest `step`.
    """
    return (_step(leverage / (1 - headroom), step),
            _step(cover * (1 - headroom), step))


def breaches(debt, ebitda, interest, max_leverage,
             min_cover) -> pd.DataFrame:
    """Test accounts against covenants, row by row.

    Leverage is debt over EBITDA; with EBITDA at or below zero it is
    infinite, and the leverage test fails. Cover is EBITDA over
    interest (infinite with no interest).
    """
    debt = np.asarray(debt, dtype="float64")
    ebitda = np.asarray(ebitda, dtype="float64")
    interest = np.asarray(interest, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        lev = np.where(ebitda > 0, debt / ebitda, np.inf)
        cov = np.where(interest > 0, ebitda / interest, np.inf)
    out = pd.DataFrame({"leverage": lev, "cover": cov})
    out["leverage_breach"] = out.leverage > np.asarray(max_leverage)
    out["cover_breach"] = out.cover < np.asarray(min_cover)
    out["breach"] = out.leverage_breach | out.cover_breach
    return out


def ebitda_headroom(leverage, cover, max_leverage,
                    min_cover) -> tuple[float, float]:
    """How far EBITDA could fall before each covenant breaks.

    Leverage breaks when EBITDA falls to debt / max_leverage, a fall
    of 1 - leverage / max_leverage; cover breaks when it falls to
    interest x min_cover, a fall of 1 - min_cover / cover. Negative
    means already in breach.
    """
    return (1 - leverage / max_leverage, 1 - min_cover / cover)


def covenant_test(s: pd.DataFrame, max_leverage: float,
                  min_cover: float) -> pd.DataFrame:
    """One company's years against a pair of covenants."""
    b = breaches(s.loc["total_debt"], s.loc["ebitda"],
                 s.loc["interest"], max_leverage, min_cover)
    b.index = s.columns
    b["leverage_headroom"], b["cover_headroom"] = ebitda_headroom(
        b.leverage, b.cover, max_leverage, min_cover)
    return b.T


def permitted_distribution(prior_net_income: int, leverage: float,
                           payout_cap: float = PAYOUT_CAP,
                           max_leverage: float = DIVIDEND_MAX_LEVERAGE,
                           in_default: bool = False) -> int:
    """The most the owners may take out this year, in cents.

    Nothing while a default is continuing, while leverage is above
    `max_leverage`, or after a loss; otherwise up to `payout_cap` of
    the previous year's net income.
    """
    if in_default or leverage > max_leverage or prior_net_income <= 0:
        return 0
    return math.floor(prior_net_income * payout_cap)


# -------------------------------------------------------- pricing

def facility_income(limit: int, drawn: int, margin_bps: int,
                    tenor_years: float = 3,
                    commitment_share: float = COMMITMENT_SHARE,
                    arrangement_pct: float = ARRANGEMENT_PCT
                    ) -> pd.Series:
    """A year's income from a revolver above the reference rate.

    The margin on what is drawn, the commitment fee (a share of the
    margin) on what is not, and the arrangement fee spread evenly
    over the tenor. Cents. The reference rate itself pays for
    Fernhill's funding and is left out.
    """
    margin = margin_bps / 10_000
    undrawn = max(limit - drawn, 0)
    parts = {
        "margin": round(drawn * margin),
        "commitment_fee": round(undrawn * margin * commitment_share),
        "arrangement_fee": round(limit * arrangement_pct
                                 / tenor_years),
    }
    parts["total"] = sum(parts.values())
    return pd.Series(parts, dtype="int64")


# ------------------------------------------------------ term sheet

@dataclass
class TermSheet:
    """The terms of one facility, as the committee will see them."""
    borrower: str
    limit_cents: int
    tenor_months: int
    purpose: str
    margin_bps: int
    reference: str
    max_leverage: float
    min_cover: float
    facility: str = "Committed revolving credit facility"
    advance_receivables: float = ADVANCE_RECEIVABLES
    advance_inventory: float = ADVANCE_INVENTORY
    commitment_share: float = COMMITMENT_SHARE
    arrangement_pct: float = ARRANGEMENT_PCT
    payout_cap: float = PAYOUT_CAP
    dividend_max_leverage: float = DIVIDEND_MAX_LEVERAGE
    security: str = ""
    guarantees: str = ""
    ranking: str = ""
    reporting: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)

    def rows(self) -> list[tuple[str, str]]:
        """(label, text) pairs, in the order a term sheet reads."""
        fee = self.margin_bps * self.commitment_share
        return [
            ("Borrower", self.borrower),
            ("Facility", self.facility),
            ("Limit", f"${self.limit_cents / 100:,.0f}"),
            ("Tenor", f"{self.tenor_months} months"),
            ("Purpose", self.purpose),
            ("Availability",
             "The lesser of the limit and the borrowing base: "
             f"{self.advance_receivables:.0%} of eligible "
             f"receivables plus {self.advance_inventory:.0%} of "
             "eligible inventory, certified monthly."),
            ("Interest", f"{self.reference} + {self.margin_bps} bps "
                         "on amounts drawn"),
            ("Fees", f"Commitment {fee:.0f} bps a year on the "
                     f"undrawn limit; arrangement "
                     f"{self.arrangement_pct:.2%} of the limit."),
            ("Security", self.security),
            ("Guarantees", self.guarantees),
            ("Ranking", self.ranking),
            ("Leverage", f"Debt / EBITDA no more than "
                         f"{self.max_leverage:.2f}x"),
            ("Interest cover", f"EBITDA / interest at least "
                               f"{self.min_cover:.2f}x"),
            ("Distributions",
             f"Up to {self.payout_cap:.0%} of the previous year's "
             "net income, only with no default and leverage at or "
             f"below {self.dividend_max_leverage:.2f}x."),
            ("Reporting", "; ".join(self.reporting)),
            ("Conditions", "; ".join(self.conditions)),
        ]


def format_term_sheet(ts: TermSheet, width: int = 68,
                      label_width: int = 16) -> list[str]:
    """The term sheet as lines of text no wider than `width`."""
    out = []
    for label, text in ts.rows():
        if not text:
            continue
        wrapped = textwrap.wrap(text, width - label_width) or [""]
        out.append(f"{label:<{label_width}}{wrapped[0]}")
        out += [" " * label_width + w for w in wrapped[1:]]
    return out
