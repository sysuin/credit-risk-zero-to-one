# Contributing to the code of *Credit Risk from Zero to One*

Thank you for looking. This repository is the companion to a book, which shapes what a
good change is here. Read this before opening a pull request.

## What this repository is

**Ballast** is the credit risk platform of Fernhill Bank, a fictional mid-sized lender,
and the worked project of *Credit Risk from Zero to One*. From ten years of Fernhill's loan book it
builds a scorecard and a decision engine, prices loans for risk, rates businesses,
estimates PD, LGD and EAD, books IFRS 9 and CECL provisions, computes Basel capital,
simulates the portfolio's losses, stress-tests it and produces a risk committee pack.

## Rules the code keeps

**Each milestone's code is kept as the book showed it.** The listings in `code/NN/` are
the book's figures in another form. Do not refactor an early chapter's code to match a
later one; the difference between them is the lesson. Some modules are printed in the
book line by line, so even a harmless edit can move the lines a chapter quotes. A bug in a
listing is a bug in the book: report it as an issue, and it will be fixed in both places.

**No output was typed by a human.** `code/_runner.py` runs every listing and saves its real
output beside it as a `.out` file. If you change a listing, run it again:

```
python3 code/_runner.py 07
```

**Every listing is deterministic.** The loan book is generated from one seed and is
identical on every machine (`code/fernhill/checksum.py` proves it); every printed result is
ordered; money is summed in integer cents; models are fitted single-threaded with their
seeds written in the code. `make verify` runs every listing twice and fails if one
character differs.

**The truth database is read only by listings about checking a method against the
answer**, and each says so on its first lines. Ballast itself never reads it.

## Before you open a pull request

```
make lint          ruff, and no captured output stale
make test          the test suite, after make data
make verify        every listing run twice, and compared
```

## Good to know

- **Disk.** The loan book is about 55 MB and the truth database about 22 MB; Ballast's
  saved results are a few MB more. Listings write scratch files only under `data/sandbox/`.
- **LightGBM on macOS** needs OpenMP: `brew install libomp`.
- **A property of the data that `code/fernhill/verify.py` does not check** is a property a
  chapter must not rely on. Add the check first.
