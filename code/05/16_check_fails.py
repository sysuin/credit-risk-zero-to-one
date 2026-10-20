# expect-fail
# A month end loaded twice, caught by the performance checks.
import pandas as pd

from ballast import data

perf = data.load_performance(products=["mortgage"])
december = perf[perf["month"] == perf["month"].max()]
again = pd.concat([perf, december], ignore_index=True)
again.attrs = perf.attrs
data.check_performance(again)
