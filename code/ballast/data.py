"""Fernhill's loan book, loaded with the right types and checked.

Three loaders, one for each table a credit model starts from:
applications, accounts and the monthly performance. Each returns a
pandas DataFrame in which

- money is integer cents (`Int64`), never a float;
- dates are dates (`date32`), so they compare with `config.AS_OF`;
- yes/no columns are booleans, nullable where "never asked" is a
  third answer;
- columns with a fixed list of values are categoricals, so a value
  nobody has seen before cannot slip in;
- every value that *means* unknown or not applicable becomes a
  missing value by a named rule in `UNKNOWNS`, and the loader records
  how many cells each rule blanked.

Then each loader runs its checks. A failed check raises
`DataCheckError`, naming every failure with a count and an example
key. Nothing is fixed quietly.

    from ballast import data
    apps = data.load_applications()
    accts = data.load_accounts()
    perf = data.load_performance(products=["personal"])
    data.check_links(apps, accts, perf)
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd
import pyarrow as pa

import fernhill
from ballast.config import AS_OF, FIRST_MONTH

FIRST_DAY = dt.date(2016, 1, 1)
# The bureau's score moved from version 2 to version 3 on this day.
BUREAU_V3_FROM = dt.date(2019, 7, 1)
# Open-banking consent: offered online from March 2021, branches 2023.
OB_OFFERED_FROM = {"online": dt.date(2021, 3, 1),
                   "branch": dt.date(2023, 1, 1)}

DATE = pd.ArrowDtype(pa.date32())

CATEGORIES = {
    "product": ["personal", "card", "auto", "mortgage", "sme_term",
                "sme_overdraft", "sme_emergency"],
    "channel": ["branch", "online", "broker", "dealer"],
    "region": ["Northgate", "Riverside", "Eastvale", "Westmoor",
               "Central", "Harbourside"],
    "employment": ["employed", "self_employed", "part_time",
                   "retired", "other"],
    "housing": ["owner", "mortgage", "renter", "with_family"],
    "bureau_version": ["v2", "v3"],
    "decision": ["approve", "decline"],
    "outcome": ["booked", "not_taken_up", "declined", "offer_open"],
    "status": ["up_to_date", "arrears", "default", "charged_off",
               "repaid", "prepaid", "closed_by_customer",
               "vehicle_repossessed", "property_sold",
               "collateral_sold"],
}
WHOLE_NUMBERS = {"age", "dependants", "open_accounts", "enquiries_6m",
                 "worst_status_24m", "public_records", "bureau_score",
                 "mark1_score", "cutoff", "ob_overdraft_days",
                 "ob_returned_payments", "missed", "days_past_due"}

BUREAU_FIELDS = ["oldest_account_months", "open_accounts",
                 "revolving_balance_cents", "enquiries_6m",
                 "worst_status_24m", "public_records"]
OB_FIELDS = ["ob_avg_balance_cents", "ob_overdraft_days",
             "ob_income_volatility", "ob_returned_payments",
             "ob_betting_share"]


class DataCheckError(Exception):
    """A table broke a rule it must keep. The message lists them all."""


# ------------------------------------------------------------- unknowns

def ob_offered(channel: pd.Series, when: pd.Series) -> pd.Series:
    """Whether open-banking consent had been offered here by then."""
    out = pd.Series(False, index=channel.index)
    for ch, start in OB_OFFERED_FROM.items():
        out |= (channel == ch) & (when >= start)
    return out


@dataclass(frozen=True)
class Unknown:
    """A stored value that means unknown or not applicable."""
    name: str
    columns: tuple[str, ...]
    meaning: str


# Where the applications table writes a value that is not a measurement.
UNKNOWNS = [
    Unknown("no_hit", tuple(BUREAU_FIELDS),
            "no file: zeros are not a clean record"),
    Unknown("not_employed", ("employment_months",),
            "retired or other: no job held"),
    Unknown("card_request", ("amount_requested_cents",
                             "term_requested_months",
                             "offered_term_months"),
            "a card has no amount or term"),
    Unknown("no_deposit_asked", ("deposit_cents",),
            "loans and cards take no deposit"),
    Unknown("ob_not_offered", ("ob_consent",),
            "never asked: False is not a no"),
]
WHERE = {
    "no_hit": lambda d: ~d["bureau_hit"],
    "not_employed": lambda d: d["employment"].isin(
        ["retired", "other"]),
    "card_request": lambda d: d["product"] == "card",
    "no_deposit_asked": lambda d: d["product"].isin(
        ["personal", "card"]),
    "ob_not_offered": lambda d: ~ob_offered(
        d["channel"], d["app_date"]),
}


def apply_unknowns(df: pd.DataFrame) -> dict[str, int]:
    """Blank what each rule says is not a measurement; count cells."""
    blanked = {}
    for rule in UNKNOWNS:
        rows = WHERE[rule.name](df).to_numpy(dtype=bool)
        n = 0
        for col in rule.columns:
            hit = rows & df[col].notna().to_numpy()
            n += int(hit.sum())
            df.loc[hit, col] = pd.NA
        blanked[rule.name] = n
    return blanked


# -------------------------------------------------------------- loading

def _typed(df: pd.DataFrame) -> pd.DataFrame:
    """Give each column the type its name and contents say it has."""
    for col in df.columns:
        s = df[col]
        if col in CATEGORIES:
            new = s.notna() & ~s.isin(CATEGORIES[col])
            if new.any():
                raise DataCheckError(
                    f"{col}: {int(new.sum()):,} values outside the "
                    f"known list, e.g. {s[new].iloc[0]!r}")
            df[col] = pd.Categorical(s, categories=CATEGORIES[col])
        elif col == "month" or col.endswith("_date"):
            df[col] = s.astype(DATE)
        elif (col.endswith("_cents") or col.endswith("_months")
              or col in WHOLE_NUMBERS):
            if pd.api.types.is_float_dtype(s):    # stored as DOUBLE
                part = s.notna() & (s != s.round())
                if part.any():
                    raise DataCheckError(
                        f"{col}: {int(part.sum()):,} values are not "
                        "whole numbers")
            df[col] = s.astype("Int64")
        elif pd.api.types.is_bool_dtype(s) or col == "ob_consent":
            df[col] = s.astype("boolean")
    return df


def _read(con, table: str, where: str = "", params=(),
          order: str = "") -> pd.DataFrame:
    con = con if con is not None else fernhill.connect()
    sql = f"SELECT * FROM {table} {where} ORDER BY {order}"
    df = _typed(con.execute(sql, list(params)).df())
    df.attrs["source_rows"] = con.execute(
        f"SELECT count(*) FROM {table} {where}",
        list(params)).fetchone()[0]
    return df


def load_applications(con=None, *, unknowns: bool = True,
                      check: bool = True) -> pd.DataFrame:
    """Every consumer application: typed, checked, unknowns blanked."""
    df = _read(con, "applications", order="app_id")
    if check:
        check_applications(df)
    df.attrs["unknowns"] = apply_unknowns(df) if unknowns else {}
    return df


def load_accounts(con=None, *, check: bool = True) -> pd.DataFrame:
    """Every account, consumer and business, typed and checked."""
    df = _read(con, "accounts", order="account_id")
    df["close_reason"] = df["close_reason"].astype("category")
    if check:
        check_accounts(df)
    return df


def load_performance(con=None, *, products=None,
                     check: bool = True) -> pd.DataFrame:
    """The monthly rows, for some products or all, typed and checked."""
    where, params = "", ()
    if products is not None:
        where, params = "WHERE product IN (SELECT unnest(?))", (
            list(products),)
    df = _read(con, "performance", where, params,
               order="account_id, month")
    if check:
        check_performance(df)
    return df


# --------------------------------------------------------------- checks

class Checks:
    """Collects every failure, so one run reports them all."""

    def __init__(self, table: str, key: str):
        self.table, self.key, self.failures = table, key, []

    def rule(self, name: str, bad, df: pd.DataFrame) -> None:
        bad = pd.Series(bad).fillna(False).to_numpy(dtype=bool)
        if bad.any():
            first = df.loc[bad, self.key].iloc[0]
            self.failures.append(
                f"  {name}: {int(bad.sum()):,} rows, e.g. {first}")

    def done(self, df: pd.DataFrame) -> None:
        held = df.attrs.get("source_rows")
        if held is not None and held != len(df):
            self.failures.append(
                f"  loaded {len(df):,} rows; the source holds {held:,}")
        if self.failures:
            raise DataCheckError(
                f"{self.table} failed {len(self.failures)} check(s):\n"
                + "\n".join(self.failures))


def _month_index(dates: pd.Series) -> pd.Series:
    """Months since the year 0: consecutive months differ by 1."""
    t = pd.to_datetime(dates.astype("datetime64[s]"))
    return t.dt.year * 12 + t.dt.month


def check_applications(df: pd.DataFrame) -> None:
    c = Checks("applications", "app_id")
    c.rule("app_id missing or repeated",
           df["app_id"].isna() | df["app_id"].duplicated(), df)
    c.rule("app_date outside 2016-2025",
           (df["app_date"] < FIRST_DAY) | (df["app_date"] > AS_OF), df)
    money = [col for col in df.columns if col.endswith("_cents")]
    c.rule("negative money", (df[money] < 0).any(axis=1), df)
    hit = df["bureau_hit"]
    c.rule("bureau hit and bureau score disagree",
           hit != df["bureau_score"].notna(), df)
    c.rule("bureau score outside 300-850",
           hit & ~df["bureau_score"].between(300, 850), df)
    version = pd.Series("v3", index=df.index).where(
        df["app_date"] >= BUREAU_V3_FROM, "v2")
    c.rule("bureau version does not match the date",
           hit & (df["bureau_version"].astype(str) != version), df)
    c.rule("verified income and the verified flag disagree",
           df["income_verified"] != df["verified_income_cents"].notna(),
           df)
    c.rule("booked and account_id disagree",
           (df["outcome"] == "booked") != df["account_id"].notna(), df)
    c.rule("outcome does not follow the decision",
           (df["decision"] == "approve")
           != (df["outcome"] != "declined"), df)
    ob = df[OB_FIELDS].notna()
    c.rule("open-banking fields part present",
           ob.any(axis=1) != ob.all(axis=1), df)
    consent = df["ob_consent"].fillna(False)
    c.rule("open-banking data and consent disagree",
           ob.any(axis=1) != consent, df)
    c.rule("consent where it was never offered",
           consent & ~ob_offered(df["channel"], df["app_date"]), df)
    c.done(df)


def check_accounts(df: pd.DataFrame) -> None:
    c = Checks("accounts", "account_id")
    ids = df["account_id"]
    c.rule("account_id missing or repeated",
           ids.isna() | ids.duplicated(), df)
    c.rule("account_id not two letters and seven digits",
           ~ids.str.fullmatch(r"[A-Z]{2}\d{7}"), df)
    c.rule("open_date outside 2016-2025",
           (df["open_date"] < FIRST_DAY) | (df["open_date"] > AS_OF),
           df)
    c.rule("closed before it opened",
           df["close_date"] < df["open_date"], df)
    c.rule("close_date and close_reason disagree",
           df["close_date"].isna() != df["close_reason"].isna(), df)
    c.rule("amount not positive", df["amount_cents"] <= 0, df)
    c.done(df)


def check_performance(df: pd.DataFrame) -> None:
    c = Checks("performance", "account_id")
    c.rule("account-month repeated",
           df.duplicated(["account_id", "month"]), df)
    t = pd.to_datetime(df["month"].astype("datetime64[s]"))
    c.rule("month is not a month end", ~t.dt.is_month_end, df)
    c.rule("month outside 2016-2025",
           (df["month"] < FIRST_MONTH) | (df["month"] > AS_OF), df)
    for col in ("balance_cents", "scheduled_cents", "paid_cents",
                "arrears_cents", "missed"):
        c.rule(f"{col} negative", df[col] < 0, df)
    c.rule("days_past_due is not 30 x missed",
           df["days_past_due"] != 30 * df["missed"], df)
    revolving = df["product"].isin(["card", "sme_overdraft"])
    c.rule("limit and product disagree",
           revolving != df["limit_cents"].notna(), df)
    span = _month_index(df["month"]).groupby(df["account_id"]).agg(
        ["min", "max", "nunique"])
    gaps = span.index[span["max"] - span["min"] + 1 != span["nunique"]]
    c.rule("a month missing inside an account's history",
           df["account_id"].isin(gaps), df)
    c.done(df)


def check_links(apps: pd.DataFrame, accounts: pd.DataFrame,
                perf: pd.DataFrame | None = None) -> None:
    """The tables agree with each other."""
    c = Checks("links", "key")
    booked = apps.loc[apps["outcome"] == "booked",
                      ["app_id", "account_id", "product"]]
    j = booked.merge(accounts[["account_id", "product"]], how="left",
                     on="account_id", suffixes=("", "_acct"),
                     indicator=True)
    j["key"] = j["app_id"]
    c.rule("booked application with no account",
           j["_merge"] == "left_only", j)
    c.rule("account's product differs from its application's",
           (j["_merge"] == "both")
           & (j["product"].astype(str)
              != j["product_acct"].astype(str)), j)
    if perf is not None:
        first = _month_index(perf["month"]).groupby(
            perf["account_id"]).min()
        products = perf["product"].unique()
        acc = accounts[accounts["product"].isin(products)]
        acc = acc.assign(key=acc["account_id"],
                         first=acc["account_id"].map(first),
                         opened=_month_index(acc["open_date"]))
        c.rule("account with no monthly rows", acc["first"].isna(), acc)
        c.rule("first monthly row is not the month it opened",
               acc["first"].notna() & (acc["first"] != acc["opened"]),
               acc)
        rows = pd.DataFrame({"key": perf["account_id"].unique()})
        c.rule("monthly rows for an account that does not exist",
               ~rows["key"].isin(accounts["account_id"]), rows)
    c.done(pd.DataFrame())
