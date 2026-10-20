"""Every listed client's Merton estimates, month by month, with the
internal grade and agency rating in force and the company's default
month, loaded once for the chapter's later listings."""
from __future__ import annotations

import pandas as pd

from ballast import market as mk


def listed_panel(con) -> pd.DataFrame:
    """mk.merton_panel plus grades, the default month (if any) and
    `before`: whole months from the month end to the default."""
    p = mk.grade_in_force(con, mk.merton_panel(con))
    d = con.execute("""SELECT company_id, default_month
                       FROM corporate_defaults""").df()
    d["default_month"] = d.default_month.dt.date
    p = p.merge(d, on="company_id", how="left")
    m, dm = pd.to_datetime(p.month), pd.to_datetime(p.default_month)
    p["before"] = (dm.dt.year - m.dt.year) * 12 \
        + (dm.dt.month - m.dt.month)
    return p


def next_year(p: pd.DataFrame, last="2024-12-31") -> pd.DataFrame:
    """Months with a whole year of history after them (to `last`),
    excluding a defaulter's default month and anything after it;
    `y` = 1 if the company defaulted in the next twelve months."""
    s = p[(pd.to_datetime(p.month) <= pd.Timestamp(last))
          & ~(p.before <= 0)].copy()
    s["y"] = s.before.between(1, 12).astype(int)
    return s.reset_index(drop=True)
