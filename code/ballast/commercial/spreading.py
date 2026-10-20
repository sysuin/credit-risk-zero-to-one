"""A company's accounts, spread: the first piece of Ballast's
commercial book.

A spread puts every company's accounts into the same lines, so that
two companies, or one company in two years, can be read side by side
and every ratio is computed the same way every time. The module:

- reads a company's years from Fernhill's `financials` table;
- derives the lines the table does not hold (gross profit, the split
  of borrowings, accruals, free cash flow), each with its assumption
  written beside it;
- checks the arithmetic, and rolls equity, fixed assets and cash
  forward from one year to the next so the gaps can be questioned;
- computes the ratios a lender reads: margins, leverage, cover, the
  debt service coverage ratio, liquidity and working-capital days;
- bridges EBITDA to operating cash flow;
- compares a company's ratios with its peers'.

    import fernhill
    from ballast.commercial import spreading as sp
    con = fernhill.connect()
    m = sp.company_id(con, "Meridian Supply Co.")
    s = sp.spread(sp.accounts(con, m))           # lines x years
    r = sp.ratios(s)                              # ratios x years
    peers = sp.peer_ratios(con, "wholesale", 2024, exclude=[m])

Money stays in integer cents until a ratio divides it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DAYS = 365
# Assumptions, used only where the accounts are silent. Each is a
# question for the borrower, and a caller can override every one.
AMORTISATION_YEARS = 5      # borrowings repaid evenly over 5 years
OCF_AFTER_INTEREST = True    # operating cash flow is after interest

RAW = ["revenue", "cogs", "opex", "ebitda", "depreciation", "ebit",
       "interest", "tax", "net_income", "cash", "receivables",
       "inventory", "current_assets", "total_assets",
       "current_liabilities", "total_debt", "equity", "capex",
       "operating_cash_flow", "payables", "dividends"]

LINES = {
    "income": [
        ("revenue", "Revenue"),
        ("cogs", "Cost of goods sold"),
        ("gross_profit", "Gross profit"),
        ("opex", "Operating expenses"),
        ("ebitda", "EBITDA"),
        ("depreciation", "Depreciation"),
        ("ebit", "Operating profit (EBIT)"),
        ("interest", "Interest"),
        ("pre_tax", "Profit before tax"),
        ("tax", "Tax"),
        ("net_income", "Net income"),
    ],
    "balance": [
        ("cash", "Cash"),
        ("receivables", "Receivables"),
        ("inventory", "Inventory"),
        ("other_current_assets", "Other current assets"),
        ("current_assets", "Current assets"),
        ("fixed_assets", "Fixed and other assets"),
        ("total_assets", "Total assets"),
        ("short_term_debt", "Borrowings due in a year"),
        ("payables", "Trade payables"),
        ("accruals", "Accruals and other"),
        ("current_liabilities", "Current liabilities"),
        ("long_term_debt", "Borrowings due later"),
        ("other_long_term", "Other long-term items"),
        ("total_liabilities", "Total liabilities"),
        ("equity", "Equity"),
        ("total_debt", "Total borrowings"),
    ],
    "cash flow": [
        ("operating_cash_flow", "Operating cash flow"),
        ("capex", "Capital expenditure"),
        ("free_cash_flow", "Free cash flow"),
        ("dividends", "Dividends paid"),
    ],
}


# --------------------------------------------------------- the spread

def company_id(con, name: str) -> str:
    """A company's id, from its name in `companies`."""
    row = con.execute("SELECT company_id FROM companies WHERE name = ?",
                      [name]).fetchone()
    if row is None:
        raise KeyError(f"no company called {name!r}")
    return row[0]


def accounts(con, company_id: str) -> pd.DataFrame:
    """A company's rows from `financials`, one per fiscal year."""
    cols = ", ".join(f"{c}_cents AS {c}" for c in RAW)
    df = con.execute(f"""
        SELECT company_id, fiscal_year, {cols}, basis
        FROM financials WHERE company_id = ?
        ORDER BY fiscal_year""", [company_id]).df()
    if df.empty:
        raise KeyError(f"no accounts for {company_id!r}")
    return df


def derive(raw: pd.DataFrame) -> pd.DataFrame:
    """Add the derived lines to rows of raw accounts (one per year).

    The table holds total borrowings and total current liabilities
    but not the borrowings inside current liabilities. The spread
    assumes a company's long-term liabilities are its borrowings,
    leases included (a fair start for a distributor with no pension
    scheme or large provisions, and a question to ask). Borrowings
    due later are then total liabilities less current liabilities,
    capped at total borrowings; the rest of the borrowings are due
    within the year; and whatever is left in current liabilities
    after trade payables and those borrowings is accruals and other
    short-term creditors.
    """
    d = raw.copy()
    d["gross_profit"] = d.revenue - d.cogs
    d["pre_tax"] = d.ebit - d.interest
    d["other_current_assets"] = (d.current_assets - d.cash
                                 - d.receivables - d.inventory)
    d["fixed_assets"] = d.total_assets - d.current_assets
    d["total_liabilities"] = d.total_assets - d.equity
    long_term = d.total_liabilities - d.current_liabilities
    d["long_term_debt"] = long_term.clip(lower=0).clip(
        upper=d.total_debt)
    d["other_long_term"] = long_term - d.long_term_debt
    d["short_term_debt"] = d.total_debt - d.long_term_debt
    d["accruals"] = (d.current_liabilities - d.short_term_debt
                     - d.payables)
    paid = 0 if OCF_AFTER_INTEREST else d.interest
    d["free_cash_flow"] = d.operating_cash_flow - d.capex - paid
    return d


def spread(raw: pd.DataFrame) -> pd.DataFrame:
    """One company's accounts as lines x fiscal years, in cents."""
    if raw.company_id.nunique() != 1:
        raise ValueError("spread one company at a time")
    d = derive(raw).set_index("fiscal_year")
    keys = list(dict.fromkeys(k for sec in LINES.values()
                              for k, _ in sec))
    s = d[keys].T.astype("int64")
    s.columns = [int(y) for y in s.columns]
    s.attrs["basis"] = dict(zip(d.index.astype(int), d.basis))
    s.attrs["company_id"] = raw.company_id.iloc[0]
    return s


SHOWN = {"audited": "audited", "management": "unaudited"}


def format_spread(s: pd.DataFrame, sections=None,
                  label_width: int = 26) -> list[str]:
    """The spread as lines of text, in thousands of dollars."""
    years = list(s.columns)
    out = [f"{'$000':<{label_width}}"
           + "".join(f"{y:>10}" for y in years),
           f"{'':<{label_width}}"
           + "".join(f"{SHOWN.get(s.attrs['basis'][y], ''):>10}"
                     for y in years)]
    for section in sections or LINES:
        out.append(section.upper())
        for key, label in LINES[section]:
            vals = "".join(f"{s.loc[key, y] / 100_000:>10,.0f}"
                           for y in years)
            out.append(f"  {label:<{label_width - 2}}{vals}")
    return out


# ------------------------------------------------------- the checks

def problems(s: pd.DataFrame, cents: int = 1) -> list[str]:
    """Arithmetic that should hold in any set of accounts, and fails.

    Each line is rounded to the cent on its own, so a total may
    differ from the sum of its parts by `cents` and still be right.
    """
    found = []
    for y in s.columns:
        c = s[y]
        tests = [
            ("EBITDA is revenue less costs",
             abs(c.ebitda - (c.revenue - c.cogs - c.opex)) <= cents),
            ("EBIT is EBITDA less depreciation",
             abs(c.ebit - (c.ebitda - c.depreciation)) <= cents),
            ("net income is EBIT less interest and tax",
             abs(c.net_income - (c.ebit - c.interest - c.tax))
             <= cents),
            ("other current assets are not negative",
             c.other_current_assets >= -cents),
            ("long-term liabilities fit inside borrowings",
             c.other_long_term == 0),
            ("accruals are not negative", c.accruals >= 0),
            ("equity is positive", c.equity > 0),
            ("EBITDA is below revenue", c.ebitda < c.revenue),
        ]
        found += [f"{y}: {name}" for name, ok in tests if not ok]
    return found


def roll_forward(s: pd.DataFrame) -> pd.DataFrame:
    """Each year's change explained by the year's flows, and the gap.

    equity_other: the change in equity less net income plus
        dividends (new shares, buy-backs, revaluations).
    fixed_other: the change in fixed assets less capex and
        depreciation (disposals, acquisitions, leases, revaluations).
    cash_other: the change in cash less free cash flow, new
        borrowing, dividends and equity_other.
    """
    prev = s.shift(1, axis=1)
    d_eq = s.loc["equity"] - prev.loc["equity"]
    d_fixed = s.loc["fixed_assets"] - prev.loc["fixed_assets"]
    d_debt = s.loc["total_debt"] - prev.loc["total_debt"]
    d_cash = s.loc["cash"] - prev.loc["cash"]
    eq_other = d_eq - s.loc["net_income"] + s.loc["dividends"]
    out = pd.DataFrame({
        "equity_change": d_eq,
        "net_income": s.loc["net_income"],
        "dividends": -s.loc["dividends"],
        "equity_other": eq_other,
        "fixed_change": d_fixed,
        "capex_less_dep": s.loc["capex"] - s.loc["depreciation"],
        "fixed_other": d_fixed - (s.loc["capex"]
                                  - s.loc["depreciation"]),
        "cash_change": d_cash,
        "free_cash_flow": s.loc["free_cash_flow"],
        "new_borrowing": d_debt,
        "cash_other": d_cash - (s.loc["free_cash_flow"] + d_debt
                                - s.loc["dividends"] + eq_other),
    }).T
    return out[s.columns[1:]]


# ------------------------------------------------------- the ratios

def _safe(a, b):
    """a / b as floats, NaN where b is zero."""
    a = pd.Series(a, dtype="float64")
    b = pd.Series(b, dtype="float64")
    return a / b.where(b != 0)


def ratio_frame(d: pd.DataFrame,
                amortisation_years: float = AMORTISATION_YEARS
                ) -> pd.DataFrame:
    """Ratios for rows of derived accounts (company-years).

    Days use year-end balances against the whole year's flows:
    receivables against revenue, inventory and trade payables against
    cost of goods sold. DSCR assumes borrowings are repaid in equal
    parts over `amortisation_years`, because summary accounts do not
    hold the repayment schedule.
    """
    r = pd.DataFrame(index=d.index)
    r["gross_margin"] = _safe(d.gross_profit, d.revenue)
    r["ebitda_margin"] = _safe(d.ebitda, d.revenue)
    r["net_margin"] = _safe(d.net_income, d.revenue)
    r["leverage"] = _safe(d.total_debt, d.ebitda)
    r["net_leverage"] = _safe(d.total_debt - d.cash, d.ebitda)
    r["interest_cover"] = _safe(d.ebitda, d.interest)
    r["ebit_cover"] = _safe(d.ebit, d.interest)
    principal = d.total_debt / amortisation_years
    r["dscr"] = dscr(d, principal)
    r["current_ratio"] = _safe(d.current_assets, d.current_liabilities)
    r["quick_ratio"] = _safe(d.cash + d.receivables,
                             d.current_liabilities)
    r["equity_ratio"] = _safe(d.equity, d.total_assets)
    r["receivable_days"] = DAYS * _safe(d.receivables, d.revenue)
    r["inventory_days"] = DAYS * _safe(d.inventory, d.cogs)
    r["payable_days"] = DAYS * _safe(d.payables, d.cogs)
    r["cash_cycle"] = (r.receivable_days + r.inventory_days
                       - r.payable_days)
    r["cash_conversion"] = _safe(d.operating_cash_flow, d.ebitda)
    r["cash_days"] = DAYS * _safe(d.cash, d.cogs + d.opex)
    r["payout"] = _safe(d.dividends, d.net_income)
    return r


def dscr(d, principal, basis: str = "ebitda") -> pd.Series:
    """Debt service coverage: cash available over interest + principal.

    basis "ebitda": EBITDA less tax less capex, the usual covenant
        form, which ignores working capital;
    basis "cash": operating cash flow less capex, what the year's
        cash actually left (interest added back if the operating
        cash flow was stated after it).
    """
    if basis == "ebitda":
        available = d.ebitda - d.tax - d.capex
    elif basis == "cash":
        available = d.operating_cash_flow - d.capex
        if OCF_AFTER_INTEREST:
            available = available + d.interest
    else:
        raise ValueError(f"unknown basis {basis!r}")
    return _safe(available, d.interest + principal)


def ratios(s: pd.DataFrame, **kw) -> pd.DataFrame:
    """One company's ratios as ratios x fiscal years."""
    r = ratio_frame(s.T, **kw).T
    growth = s.loc["revenue"] / s.loc["revenue"].shift(1) - 1
    return pd.concat([pd.DataFrame([growth], index=["revenue_growth"]),
                      r])


def cash_bridge(s: pd.DataFrame) -> pd.DataFrame:
    """From EBITDA to operating cash flow, through working capital.

    Operating cash flow should be EBITDA, less tax paid (and less
    interest, if the company reports it there), less the growth in
    receivables and inventory, plus the growth in trade payables and
    accruals. The difference between that and the reported figure is
    `unexplained`: timing of tax, other receivables, provisions,
    or something the summary does not show.
    """
    prev = s.shift(1, axis=1)
    out = pd.DataFrame({
        "ebitda": s.loc["ebitda"],
        "tax": -s.loc["tax"],
        "receivables": -(s.loc["receivables"]
                         - prev.loc["receivables"]),
        "inventory": -(s.loc["inventory"] - prev.loc["inventory"]),
        "payables": s.loc["payables"] - prev.loc["payables"],
        "accruals": s.loc["accruals"] - prev.loc["accruals"],
    })
    if OCF_AFTER_INTEREST:
        out.insert(1, "interest", -s.loc["interest"])
    out["derived"] = out.sum(axis=1)
    out["reported"] = s.loc["operating_cash_flow"]
    out["unexplained"] = out.reported - out.derived
    return out.T[s.columns[1:]]


# -------------------------------------------------------- the peers

def peer_accounts(con, sector: str, fiscal_year: int,
                  exclude=()) -> pd.DataFrame:
    """Derived accounts for every company in a sector, one year."""
    cols = ", ".join(f"f.{c}_cents AS {c}" for c in RAW)
    df = con.execute(f"""
        SELECT f.company_id, f.fiscal_year, {cols}, f.basis
        FROM financials f JOIN companies c USING (company_id)
        WHERE c.sector = ? AND f.fiscal_year = ?
        ORDER BY f.company_id""", [sector, fiscal_year]).df()
    df = df[~df.company_id.isin(list(exclude))]
    return derive(df).set_index("company_id")


def peer_ratios(con, sector: str, fiscal_year: int, exclude=(),
                **kw) -> pd.DataFrame:
    """Ratios for every company in a sector, one row per company."""
    return ratio_frame(peer_accounts(con, sector, fiscal_year,
                                     exclude), **kw)


def compare(target: pd.Series, peers: pd.DataFrame,
            names=None) -> pd.DataFrame:
    """Where a company's ratios sit among its peers'.

    For each ratio: the company's value, the peers' quartiles, and
    the share of peers below the company (ties count half).
    """
    rows = []
    for name in names or list(peers.columns):
        p = peers[name].dropna().to_numpy()
        v = float(target[name])
        below = ((p < v).sum() + 0.5 * (p == v).sum()) / len(p)
        rows.append({"ratio": name, "value": v,
                     "p25": float(np.percentile(p, 25)),
                     "median": float(np.median(p)),
                     "p75": float(np.percentile(p, 75)),
                     "share_below": float(below), "n": len(p)})
    return pd.DataFrame(rows).set_index("ratio")
