"""Mark II's sample: which loans, which window, which definition of bad.

A scorecard is fitted to loans whose outcome is known, and every
choice about which loans and which outcome is a choice about what the
scorecard will learn. This module makes those choices once, in code,
so that Chapters 7 to 13 fit and test on the same rows:

- booked personal loans, each the account opened from its application;
- the outcome window: the first twelve payments due (months on book
  1 to 12);
- bad: three or more payments missed in the window (90 days past
  due), on the plain dpd90 definition throughout; indeterminate: at
  worst exactly two missed; good: everything else;
- development: applications 2016 to 2022, with a random 30% held out;
  out-of-time: January 2023 to June 2024; later ones are too recent;
- bureau scores of version 2 mapped onto version 3's scale;
- payment holidays inside the window flagged, not removed.

    from ballast.scorecard import sample
    s = sample.build_sample()
    sample.save_sample(s)            # data/ballast/mark2/
    s = sample.load_sample()         # what Chapter 8 starts from
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fernhill
from ballast import data
from ballast.config import AS_OF, BALLAST, SEED

PRODUCT = "personal"
DEV_FROM, DEV_TO = dt.date(2016, 1, 1), dt.date(2022, 12, 31)
OOT_FROM, OOT_TO = dt.date(2023, 1, 1), dt.date(2024, 6, 30)
HOLDOUT_SHARE = 0.30
WINDOW = 12                 # payments due: months on book 1 to 12
BAD_MISSED = 3              # three missed payments: 90 days past due
INDETERMINATE_MISSED = 2    # 60 days at worst, never 90
# Version 2 scores are matched to version 3 on the same population:
# applicants in the six months either side of the change.
V2_HALF = (dt.date(2019, 1, 1), dt.date(2019, 6, 30))
V3_HALF = (dt.date(2019, 7, 1), dt.date(2019, 12, 31))
# The rate at which every applicant's new instalment is worked out
# for the debt-to-income ratio: Fernhill's flat personal-loan price
# before 2019, so the ratio means the same in every year.
ASSESSMENT_RATE = 10.9
MARK2 = BALLAST / "mark2"

CLOSED = ("repaid", "prepaid", "closed_by_customer", "charged_off")

# The candidate characteristics: known on the day of the application.
NUMERIC = ["bureau_score", "oldest_account_months", "open_accounts",
           "revolving_utilisation", "revolving_balance",
           "enquiries_6m", "worst_status_24m", "public_records", "dti",
           "income", "amount_requested", "term_requested_months",
           "age", "employment_months", "address_months", "dependants"]
CATEGORICAL = ["employment", "housing", "purpose", "channel", "region"]
CHARACTERISTICS = NUMERIC + CATEGORICAL
# What a missing value means, characteristic by characteristic. Each
# becomes a bin of its own.
NO_FILE = "no file"
MISSING_LABEL = {
    **{c: NO_FILE for c in ["bureau_score", "oldest_account_months",
                            "open_accounts", "revolving_utilisation",
                            "revolving_balance", "enquiries_6m",
                            "worst_status_24m", "public_records",
                            "dti"]},
    "employment_months": "not employed",
}
# The direction the bad rate is expected to move as each rises, where
# experience says which; the others take the data's own direction.
TRENDS = {
    "bureau_score": "decreasing", "oldest_account_months": "decreasing",
    "revolving_utilisation": "increasing", "enquiries_6m": "increasing",
    "worst_status_24m": "increasing", "public_records": "increasing",
    "dti": "increasing", "income": "decreasing",
    "employment_months": "decreasing", "address_months": "decreasing",
}
# Fine cut points rounded to something a person would write.
DECIMALS = {"bureau_score": -1, "revolving_utilisation": 2, "dti": 2,
            "income": -3, "amount_requested": -3,
            "revolving_balance": -2}
# Everything binning.bin_all needs, characteristic by characteristic.
BINNING = {
    name: {"kind": "categorical" if name in CATEGORICAL else "numeric",
           "missing": MISSING_LABEL.get(name),
           "trend": TRENDS.get(name, "auto"),
           "decimals": DECIMALS.get(name)}
    for name in CHARACTERISTICS}
# Known at application, and still not candidates.
LEFT_OUT = {
    "ob_*": "bank-account data: only consenting online applicants "
            "since March 2021 and branch applicants since 2023",
    "gender": "collected for fair-lending monitoring, never used",
    "mark1_score": "the scorecard being replaced",
    "income_verified": "set by Fernhill's verification rules",
    "bureau_retro": "known up to eighteen months after the decision",
}


# ------------------------------------------------------------ outcomes

OUTCOME_SQL = f"""
WITH booked AS (
    SELECT a.app_id, c.account_id, c.open_date, c.close_date
    FROM applications a
    JOIN accounts c ON c.account_id = a.account_id
    WHERE a.product = ? AND a.outcome = 'booked'
      AND c.predecessor_id IS NULL),
win AS (
    SELECT b.account_id,
           max(p.missed) AS worst_missed,
           max(datediff('month', b.open_date, p.month)) AS last_mob,
           bool_or(p.status IN {CLOSED}) AS closed,
           bool_or(p.payment_holiday) AS holiday
    FROM booked b
    JOIN performance p ON p.account_id = b.account_id
    WHERE datediff('month', b.open_date, p.month)
          BETWEEN 1 AND {WINDOW}
    GROUP BY b.account_id)
SELECT b.app_id, b.account_id, b.open_date,
       coalesce(w.worst_missed, 0) AS worst_missed,
       coalesce(w.last_mob, 0) AS last_mob,
       coalesce(w.closed, FALSE)
         OR (b.close_date IS NOT NULL AND
             datediff('month', b.open_date, b.close_date)
             <= {WINDOW}) AS closed_in_window,
       coalesce(w.holiday, FALSE) AS holiday
FROM booked b LEFT JOIN win w USING (account_id)
ORDER BY b.app_id
"""


def outcomes(con=None, product: str = PRODUCT) -> pd.DataFrame:
    """Each booked loan's worst arrears in its first twelve payments.

    `outcome` is bad (three or more missed), indeterminate (exactly
    two at worst) or good; `complete` says whether the window has
    finished, by reaching month on book 12 or by the loan closing.
    """
    con = con if con is not None else fernhill.connect()
    df = con.execute(OUTCOME_SQL, [product]).df()
    df["open_date"] = df["open_date"].astype(data.DATE)
    df["complete"] = (df["last_mob"] >= WINDOW) | df["closed_in_window"]
    df["outcome"] = np.select(
        [df["worst_missed"] >= BAD_MISSED,
         df["worst_missed"] == INDETERMINATE_MISSED],
        ["bad", "indeterminate"], "good")
    df["bad"] = (df["outcome"] == "bad").astype(int)
    return df


# --------------------------------------------------------- bureau score

def bureau_map(apps: pd.DataFrame) -> pd.Series:
    """A version-3 score for every version-2 score, by percentile.

    Each v2 score from 300 to 850 is given the v3 score found at the
    same percentile: v2 among applicants of January to June 2019,
    v3 among applicants of July to December 2019.
    """
    def scores(half):
        d = apps["app_date"]
        sel = ((d >= half[0]) & (d <= half[1])
               & apps["bureau_hit"]).to_numpy(dtype=bool)
        return apps.loc[sel, "bureau_score"].astype(float).to_numpy()

    v2, v3 = np.sort(scores(V2_HALF)), np.sort(scores(V3_HALF))
    grid = np.arange(300, 851)
    # Mid-rank percentile: the share below, plus half the share equal.
    below = np.searchsorted(v2, grid, side="left")
    upto = np.searchsorted(v2, grid, side="right")
    pct = (below + upto) / 2 / len(v2)
    mapped = np.quantile(v3, np.clip(pct, 0, 1))
    return pd.Series(np.round(mapped).astype(int), index=grid,
                     name="v3_score").rename_axis("v2_score")


def harmonised_bureau(apps: pd.DataFrame,
                      mapping: pd.Series) -> pd.Series:
    """Bureau score on version 3's scale, whichever it came on."""
    score = apps["bureau_score"]
    v2 = apps["bureau_version"].astype(str).eq("v2") & score.notna()
    out = score.astype("Float64")
    out[v2] = score[v2].astype(int).map(mapping).astype(float)
    return out


# ------------------------------------------------------ characteristics

def instalment(amount_cents: pd.Series, term: pd.Series,
               rate_pct: float = ASSESSMENT_RATE) -> pd.Series:
    """The level monthly payment, in cents, on what was asked for."""
    r = rate_pct / 1200
    t = term.astype(float)
    return amount_cents.astype(float) * r / (1 - (1 + r) ** -t)


def characteristics(apps: pd.DataFrame,
                    mapping: pd.Series) -> pd.DataFrame:
    """Every candidate characteristic, as known on the application day.

    Money is in dollars here: a characteristic is binned, never summed.
    """
    a = apps
    hit = a["bureau_hit"].astype(bool)
    income = a["verified_income_cents"].fillna(a["stated_income_cents"])
    pay = instalment(a["amount_requested_cents"],
                     a["term_requested_months"])
    dti = (a["other_payments_cents"].astype(float) + pay) / (
        income.astype(float) / 12)
    out = pd.DataFrame({
        "app_id": a["app_id"],
        "bureau_score": harmonised_bureau(a, mapping),
        "oldest_account_months": a["oldest_account_months"],
        "open_accounts": a["open_accounts"],
        "revolving_utilisation": a["revolving_utilisation"],
        "revolving_balance": a["revolving_balance_cents"] / 100,
        "enquiries_6m": a["enquiries_6m"],
        "worst_status_24m": a["worst_status_24m"],
        "public_records": a["public_records"],
        # The bureau reports no other payments for an applicant it does
        # not know, so their ratio is not measured.
        "dti": dti.where(hit),
        "income": income / 100,
        "amount_requested": a["amount_requested_cents"] / 100,
        "term_requested_months": a["term_requested_months"],
        "age": a["age"],
        "employment_months": a["employment_months"],
        "address_months": a["address_months"],
        "dependants": a["dependants"],
    })
    for col in CATEGORICAL:
        out[col] = a[col].astype(str)
    for col in NUMERIC:
        out[col] = out[col].astype("float64")
    return out.reset_index(drop=True)


# ---------------------------------------------------------- the sample

def period(app_date: pd.Series) -> pd.Series:
    """development, out_of_time, too_recent (or None before 2016)."""
    d = app_date
    when = [((d >= DEV_FROM) & (d <= DEV_TO)),
            ((d >= OOT_FROM) & (d <= OOT_TO)), d > OOT_TO]
    return pd.Series(np.select(
        [w.to_numpy(dtype=bool) for w in when],
        ["development", "out_of_time", "too_recent"], ""),
        index=d.index)


def holdout(app_ids: pd.Series) -> pd.Series:
    """A random 30% of the given loans, the same on every run."""
    order = np.argsort(app_ids.to_numpy())
    n = len(order)
    rng = np.random.default_rng(SEED)
    pick = order[rng.permutation(n)[: round(HOLDOUT_SHARE * n)]]
    out = np.zeros(n, dtype=bool)
    out[pick] = True
    return pd.Series(out, index=app_ids.index)


def build_sample(con=None, apps: pd.DataFrame | None = None,
                 ) -> pd.DataFrame:
    """Mark II's sample: one row per booked personal loan to June 2024.

    `split` is train, holdout or out_of_time; `outcome` is good, bad
    or indeterminate; `fit` marks the rows a model is fitted to (train
    and not indeterminate). Every candidate characteristic follows.
    """
    con = con if con is not None else fernhill.connect()
    apps = apps if apps is not None else data.load_applications(con)
    mapping = bureau_map(apps)
    booked = apps[(apps["product"] == PRODUCT)
                  & (apps["outcome"] == "booked")
                  & (apps["app_date"] >= DEV_FROM)
                  & (apps["app_date"] <= OOT_TO)]
    out = outcomes(con).merge(
        booked[["app_id", "app_date"]], on="app_id", how="inner")
    out["period"] = period(out["app_date"])
    dev = out["period"] == "development"
    out["split"] = np.where(dev, "train", "out_of_time")
    out.loc[dev & holdout(out.loc[dev, "app_id"]).reindex(
        out.index, fill_value=False), "split"] = "holdout"
    out["fit"] = (out["split"] == "train") & (
        out["outcome"] != "indeterminate")
    chars = characteristics(booked, mapping)
    out = out.merge(chars, on="app_id", how="left", validate="1:1")
    if not out["complete"].all():
        raise ValueError("a loan in the sample has an open window")
    out.attrs["bureau_map"] = mapping
    cols = ["app_id", "account_id", "app_date", "open_date", "split",
            "outcome", "bad", "fit", "worst_missed", "holiday"]
    return out[cols + CHARACTERISTICS].sort_values(
        "app_id").reset_index(drop=True)


def summary(s: pd.DataFrame) -> pd.DataFrame:
    """Loans, bads, indeterminates and holidays by split."""
    g = s.groupby("split", sort=False)
    t = pd.DataFrame({
        "loans": g.size(),
        "bads": g["bad"].sum(),
        "indeterminate": g["outcome"].apply(
            lambda o: int((o == "indeterminate").sum())),
        "holiday": g["holiday"].sum(),
    })
    t = t.reindex(["train", "holdout", "out_of_time"])
    t["bad_rate"] = t["bads"] / (t["loans"] - t["indeterminate"])
    return t


def definition() -> dict:
    """The sample's rules, as data: what a validator reads first."""
    return {
        "product": PRODUCT,
        "population": "booked, the account opened from the application",
        "window": f"months on book 1-{WINDOW}",
        "bad": f"worst missed >= {BAD_MISSED} (dpd90 throughout)",
        "indeterminate": f"worst missed == {INDETERMINATE_MISSED}",
        "good": "everything else, including loans repaid early",
        "development": [str(DEV_FROM), str(DEV_TO)],
        "holdout_share": HOLDOUT_SHARE,
        "holdout_seed": SEED,
        "out_of_time": [str(OOT_FROM), str(OOT_TO)],
        "too_recent_from": str(OOT_TO + dt.timedelta(days=1)),
        "bureau": "v2 mapped to v3 by percentile, "
                  f"{V2_HALF[0]}..{V2_HALF[1]} vs "
                  f"{V3_HALF[0]}..{V3_HALF[1]}",
        "assessment_rate_pct": ASSESSMENT_RATE,
        "payment_holidays": "kept, flagged in `holiday`",
        "characteristics": CHARACTERISTICS,
        "missing_label": MISSING_LABEL,
        "left_out": LEFT_OUT,
        "as_of": str(AS_OF),
    }


def save_sample(s: pd.DataFrame, path: Path = MARK2) -> list[Path]:
    """Write the sample, its definition and the bureau map."""
    path.mkdir(parents=True, exist_ok=True)
    files = [path / "sample.parquet", path / "sample.json",
             path / "bureau_v2_to_v3.csv"]
    plain = s.copy()
    plain.attrs = {}
    plain.to_parquet(files[0], index=False)
    counts = summary(s)
    spec = definition() | {"counts": {
        k: {c: (round(float(v), 6) if c == "bad_rate" else int(v))
            for c, v in row.items()}
        for k, row in counts.iterrows()}}
    files[1].write_text(json.dumps(spec, indent=2) + "\n")
    s.attrs["bureau_map"].to_csv(files[2])
    return files


def load_sample(path: Path = MARK2) -> pd.DataFrame:
    """The sample as Chapter 7 saved it."""
    s = pd.read_parquet(path / "sample.parquet")
    for col in ("app_date", "open_date"):
        s[col] = s[col].astype(data.DATE)
    m = pd.read_csv(path / "bureau_v2_to_v3.csv", index_col=0)
    s.attrs["bureau_map"] = m["v3_score"]
    return s
