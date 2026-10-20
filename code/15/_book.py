"""Fernhill's commercial book, loaded once for the covenant listings.

Each fiscal year's accounts are taken to reach Fernhill by 31 March of
the following year, the date of its annual review; a company-year
counts only if its accounts arrived before the company defaulted.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd


def arrives(fy: int) -> dt.date:
    """When a fiscal year's accounts reach Fernhill's review."""
    return dt.date(fy + 1, 3, 31)


def latest_year(day: dt.date) -> int:
    """The fiscal year of the latest accounts Fernhill held on `day`."""
    return day.year - 1 if day >= dt.date(day.year, 3, 31) \
        else day.year - 2


def accounts(con) -> pd.DataFrame:
    """Every client's company-years, with sector and default month,
    and with `k`: 1 for a defaulter's last accounts before default,
    2 for the year before, and so on (missing for non-defaulters)."""
    acc = con.execute("""
        SELECT f.company_id, c.sector, f.fiscal_year AS fy,
               f.total_debt_cents AS debt, f.ebitda_cents AS ebitda,
               f.interest_cents AS interest, d.default_month AS dm
        FROM financials f
        JOIN companies c USING (company_id)
        LEFT JOIN corporate_defaults d USING (company_id)
        WHERE c.client_since IS NOT NULL
          AND (d.default_month IS NULL
               OR make_date(f.fiscal_year + 1, 3, 31)
                  < d.default_month)
        ORDER BY 1, 3""").df()
    acc["dm"] = acc.dm.dt.date
    acc["k"] = acc[acc.dm.notna()].groupby("company_id").fy.rank(
        ascending=False)
    return acc


def facilities(con) -> pd.DataFrame:
    """Every facility with its dates and covenants."""
    fac = con.execute("""
        SELECT facility_id, company_id, start_date, maturity_date,
               covenant_max_leverage AS cap,
               covenant_min_interest_cover AS floor
        FROM facilities ORDER BY facility_id""").df()
    for col in ("start_date", "maturity_date"):
        fac[col] = fac[col].dt.date
    return fac


def live_years(acc: pd.DataFrame, fac: pd.DataFrame) -> pd.DataFrame:
    """Each company-year joined to every facility that was live when
    its accounts arrived."""
    j = acc.merge(fac, on="company_id")
    when = j.fy.map(arrives)
    keep = (j.start_date <= when) & (when <= j.maturity_date)
    return j[keep].reset_index(drop=True)


def rates(cy: pd.DataFrame, col: str = "breach") -> list[float]:
    """Share in breach: defaulters' last, -1 and -2 accounts, then
    every company-year of companies that never defaulted."""
    out = [cy[cy.k == k][col].mean() for k in (1, 2, 3)]
    return out + [cy[cy.k.isna()][col].mean()]
