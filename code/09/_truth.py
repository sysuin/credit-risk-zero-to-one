"""Every applicant's outcome, including the ones Fernhill never saw.

What a simulator knows and a bank never can. For a booked loan the
outcome is the one in Fernhill's books: three or more payments missed
in the first twelve. For an applicant Fernhill declined, or approved
and lost, it is the simulator's answer to "would they have gone bad
within twelve months had Fernhill lent on its standard terms?" Used
only to score methods, never as an input to one.
"""
import numpy as np

import fernhill
from ballast.scorecard import reject, sample


def with_truth(a):
    """`a` (from reject.applicants) with a `truth` column, 1 = bad."""
    truth = fernhill.connect(truth=True)
    t = truth.execute("""
        SELECT app_id, bad_12m_if_booked::DOUBLE AS would_be_bad
        FROM origination ORDER BY app_id""").df()
    worst = sample.load_sample()[["app_id", "worst_missed"]]
    out = a.merge(t, on="app_id", how="left", validate="1:1")
    out = out.merge(worst, on="app_id", how="left", validate="1:1")
    booked_bad = (out["worst_missed"] >= sample.BAD_MISSED)
    out["truth"] = np.where(out["known"], booked_bad.astype(float),
                            out["would_be_bad"])
    if out["truth"].isna().any():
        raise ValueError("an applicant without a true outcome")
    return out.drop(columns=["would_be_bad", "worst_missed"])


def applicants_with_truth():
    return with_truth(reject.applicants())
