"""The tables in ``eval-censoring.md`` and ``optimizer-budget-study.md``, pinned.

Both are backed by committed CSVs, so their tables are recomputed from the runs
rather than compared to a summary. These two documents exist because a metric was
being read without its censoring, so the counts that establish the censoring are the
part most worth gating.

**Note the two documents use different standard deviations.** The budget study
publishes the *sample* sd (ddof=1); `slack-free-encoding.md` publishes the
*population* sd for the same kind of quantity. Neither is wrong, and computing the
other one gives a near-miss that reads exactly like a transcription error, so each is
checked with its own convention and this comment is why.

One thing here is **not** reproducible and is left uncovered: the cap-lift strata
table splits its middle rows by whether *some restarts* were capped, and the CSV
records only each cell's total evaluation count. The fully-censored row and the
converged row's exact-zero floor are checked; the 3/4 split between "partially
censored" and "converged" is not recoverable from the committed data.
"""

from __future__ import annotations

import csv
import re
import statistics as st
from pathlib import Path

import pytest

from _markdown import flatten, markdown_table as _markdown_table, numbers

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs" / "results"

CENSORING = (RESULTS / "eval-censoring.md").read_text()
BUDGET = (RESULTS / "optimizer-budget-study.md").read_text()
CENSORING_FLAT = flatten(CENSORING)
BUDGET_FLAT = flatten(BUDGET)

#: The pre-registered concentration bar, as `slack-free-encoding.md` defines it.
BAR = 5 / 2**6

CAP = 1000  # the maxiter=200 x n_starts=5 evaluation cap these sweeps ran under


def load(name: str) -> list[dict]:
    with (RESULTS / name).open() as handle:
        return list(csv.DictReader(handle))


def by_cell(rows: list[dict]) -> dict[tuple[int, int, int], dict]:
    """Sweep rows keyed by the cell they describe: (T, seed, reps)."""
    return {(int(r["T"]), int(r["seed"]), int(r["reps"])): r for r in rows}


ALPHA_STAR_ARM = by_cell(load("qaoa_scaling_alphastar_T5.csv"))
DEFAULT_ARM = by_cell(load("qaoa_scaling_T5.csv"))
ALPHA_STAR_LIFTED = by_cell(load("qaoa_scaling_alphastar_T5_maxiter1000.csv"))

ARMS = {"alpha_star": ALPHA_STAR_ARM, "default": DEFAULT_ARM}


def arm_key(label: str) -> str:
    """Which arm a row label names. The α\\* label carries markdown escaping."""
    return "default" if "default" in label else "alpha_star"


# --- eval-censoring.md -----------------------------------------------------------


def census_rows() -> list[tuple[str, list[str]]]:
    _, rows = _markdown_table(CENSORING, "| cells at exactly 1000 evals |")
    return [(arm_key(r[0]), r) for r in rows]


CENSUS_ROWS = census_rows()


@pytest.mark.parametrize(
    "arm,row", CENSUS_ROWS, ids=[a for a, _ in CENSUS_ROWS]
)
def test_census_table_row(arm, row):
    """Cells at the cap, per reps stratum and in total, recounted from the sweep.

    This table is the document's foundation: the published 1.17x ratio was defended
    as a lower bound because its numerator was censored, and the finding is that the
    denominator is censored too. If these counts drift, that argument dissolves.
    """
    cells = ARMS[arm]
    total_censored = total_cells = 0

    for column, reps in enumerate([1, 2, 3], start=1):
        stratum = [r for (_, _, rep), r in cells.items() if rep == reps]
        censored = sum(1 for r in stratum if int(r["qaoa_evals"]) == CAP)
        published, out_of = (int(n) for n in numbers(row[column])[:2])
        assert (censored, len(stratum)) == (published, out_of), f"reps={reps}"
        total_censored += censored
        total_cells += len(stratum)

    published_total, published_out_of = (int(n) for n in numbers(row[4])[:2])
    assert (total_censored, total_cells) == (published_total, published_out_of)


def test_both_arms_are_censored_which_is_the_documents_point():
    """"It is worse than a lower bound. The denominator is censored too."""
    for arm, cells in ARMS.items():
        censored = sum(1 for r in cells.values() if int(r["qaoa_evals"]) == CAP)
        assert censored > 0, f"{arm} shows no censoring, which is the document's premise"


def clean_pairs(reps: int) -> list[tuple[int, int, int]]:
    """Cells where neither arm hit the cap -- the only unbiased comparison available."""
    return [
        cell
        for cell in ALPHA_STAR_ARM
        if cell[2] == reps
        and int(ALPHA_STAR_ARM[cell]["qaoa_evals"]) < CAP
        and int(DEFAULT_ARM[cell]["qaoa_evals"]) < CAP
    ]


def stratum_rows() -> list[tuple[int, list[str]]]:
    _, rows = _markdown_table(CENSORING, "| stratum | clean pairs |")
    return [(int(numbers(r[0])[0]), r) for r in rows]


STRATUM_ROWS = stratum_rows()


@pytest.mark.parametrize(
    "reps,row", STRATUM_ROWS, ids=[f"reps{r}" for r, _ in STRATUM_ROWS]
)
def test_clean_pair_stratum_row(reps, row):
    """Clean-pair counts and the eval ratio, recomputed.

    The ratio is the **mean of per-cell ratios**, which is the pooling the document
    names in the paragraph above the table; the ratio of totals gives 0.542 at reps=1
    against a published 0.593, so picking the wrong one looks like a wrong number.
    """
    clean = clean_pairs(reps)
    published_clean, published_total = (int(n) for n in numbers(row[1])[:2])
    assert len(clean) == published_clean
    assert published_total == sum(1 for cell in ALPHA_STAR_ARM if cell[2] == reps)

    ratio = numbers(row[2])[0] if any(c.isdigit() for c in row[2]) else None
    if not clean:
        assert ratio is None, "a stratum with no clean pairs cannot report a ratio"
        assert "not estimable" in row[3]
        return

    measured = st.mean(
        int(ALPHA_STAR_ARM[c]["qaoa_evals"]) / int(DEFAULT_ARM[c]["qaoa_evals"])
        for c in clean
    )
    assert f"{measured:.3f}" == f"{ratio:.3f}"


def test_the_reps_one_headline_percentage():
    """"α* converges in ~41% fewer evaluations than default weights" at reps=1."""
    percent = int(re.search(r"~(\d+)% \*?fewer\*? evaluations", CENSORING_FLAT).group(1))
    clean = clean_pairs(1)
    ratio = st.mean(
        int(ALPHA_STAR_ARM[c]["qaoa_evals"]) / int(DEFAULT_ARM[c]["qaoa_evals"])
        for c in clean
    )
    assert round((1 - ratio) * 100) == percent


def cap_lift_rows() -> list[tuple[int, list[str]]]:
    _, rows = _markdown_table(CENSORING, "| cell | evals | ideal mass |")
    return [(int(numbers(r[0])[0]), r) for r in rows]


CAP_LIFT_ROWS = cap_lift_rows()


@pytest.mark.parametrize(
    "slots,row", CAP_LIFT_ROWS, ids=[f"T{t}" for t, _ in CAP_LIFT_ROWS]
)
def test_cap_lift_cell_row(slots, row):
    """The reps=3 cells before and after the cap lift, both columns.

    The mass column is ``ideal_opt_mass``, not ``opt_prob_mass``: the sampled column
    gives 0.0813 → 0.1768 where the document publishes 0.0909 → 0.1879, which is the
    kind of near-agreement that would let a wrong column look right.
    """
    cell = (slots, 0, 3)
    before, after = ALPHA_STAR_ARM[cell], ALPHA_STAR_LIFTED[cell]

    evals_before, evals_after = (int(n) for n in numbers(row[1])[:2])
    assert evals_before == int(before["qaoa_evals"]) == CAP
    assert evals_after == int(after["qaoa_evals"])

    # The mass endpoints are plain decimals except on the T=5 row, which prints
    # "1.7x10^-5 -> ~0" -- a magnitude and an approximation rather than two figures.
    # Those two are checked as what they claim (order of magnitude, and a collapse
    # toward zero) instead of being forced into a decimal comparison.
    endpoints = re.findall(r"(?<![\d.×^-])(\d+\.\d+)(?![\d×])", row[2])
    measured = [float(before["ideal_opt_mass"]), float(after["ideal_opt_mass"])]

    if len(endpoints) == 2:
        for value, printed in zip(measured, endpoints):
            digits = len(printed.split(".")[1])
            assert f"{value:.{digits}f}" == printed
        return

    magnitude = re.search(r"([\d.]+)×10⁻⁵", row[2])
    assert magnitude, f"unhandled mass cell: {row[2]!r}"
    assert f"{measured[0] * 1e5:.1f}" == magnitude.group(1)
    assert "~0" in row[2] and measured[1] < measured[0] / 100


def test_the_fully_censored_stratum_and_the_zero_floor():
    """The dose-response table's two ends, both recomputable; its middle is not.

    "Fully censored" is every cell that sat on the cap, and it reproduces exactly.
    The converged end is checked as the property the document claims -- cells that
    used no extra budget returned bit-identical mass. The partial/converged *split*
    needs per-restart censoring, which the CSV does not record, so it is not gated.
    """
    _, rows = _markdown_table(CENSORING, "| α\\* stratum | n |")
    fully = next(r for r in rows if "fully censored" in r[0])

    capped = [c for c in ALPHA_STAR_LIFTED if c[1] == 0 and int(ALPHA_STAR_ARM[c]["qaoa_evals"]) == CAP]
    deltas = [
        abs(float(ALPHA_STAR_LIFTED[c]["ideal_opt_mass"]) - float(ALPHA_STAR_ARM[c]["ideal_opt_mass"]))
        / float(ALPHA_STAR_ARM[c]["ideal_opt_mass"])
        * 100
        for c in capped
    ]
    assert int(numbers(fully[1])[0]) == len(capped)
    assert f"{st.median(deltas):.1f}" == f"{numbers(fully[2])[0]:.1f}"
    assert f"{max(deltas):.1f}" == f"{numbers(fully[3])[0]:.1f}"

    unchanged = [
        c
        for c in ALPHA_STAR_LIFTED
        if c[1] == 0 and int(ALPHA_STAR_LIFTED[c]["qaoa_evals"]) == int(ALPHA_STAR_ARM[c]["qaoa_evals"])
    ]
    assert unchanged, "the document claims some cells used no extra budget"
    for cell in unchanged:
        assert ALPHA_STAR_LIFTED[cell]["ideal_opt_mass"] == ALPHA_STAR_ARM[cell]["ideal_opt_mass"], (
            "a cell that used no extra budget must return bit-identical mass"
        )


# --- optimizer-budget-study.md ---------------------------------------------------

BUDGET_RUNS: dict[tuple[str, str], list[dict]] = {}
for _row in load("optimizer_budget.csv"):
    BUDGET_RUNS.setdefault((_row["alpha"], _row["arm"]), []).append(_row)


def harness_rows() -> list[tuple[str, str, list[str]]]:
    _, rows = _markdown_table(BUDGET, "| arm | α | reproduced |")
    return [(r[0].split("`")[1], f"{numbers(r[1])[0]:g}", r) for r in rows]


HARNESS_ROWS = harness_rows()


@pytest.mark.parametrize(
    "arm,alpha,row",
    HARNESS_ROWS,
    ids=[f"{a}-{al}" for a, al, _ in HARNESS_ROWS],
)
def test_harness_reproduction_row(arm, alpha, row):
    """The harness check: this study must reproduce the original study's arms.

    That gate is what makes the new comparison trustworthy, so it is checked against
    the runs rather than taken from the "OK" column -- which is itself asserted to
    say OK, since a table reporting a mismatch as OK is the failure it exists to stop.
    """
    reproduced, original = float(row[2]), float(row[3])
    masses = [float(r["ideal_mass"]) for r in BUDGET_RUNS[(alpha, arm)]]
    assert f"{st.mean(masses):.5f}" == f"{reproduced:.5f}"
    assert f"{reproduced:.5f}" == f"{original:.5f}", "the harness check has drifted"
    assert row[4].strip() == "OK"


def ladder_rows() -> list[tuple[str, list[str]]]:
    _, rows = _markdown_table(BUDGET, "| arm (α=0.021) | cap |")
    return [(r[0].split("`")[1], r) for r in rows]


LADDER_ROWS = ladder_rows()


@pytest.mark.parametrize("arm,row", LADDER_ROWS, ids=[a for a, _ in LADDER_ROWS])
def test_budget_ladder_row(arm, row):
    """Cap, actual spend, mean, sd and clears, all recomputed from the runs.

    The spend percentage is the study's actual finding -- the best-funded arm stops
    at 38% of its cap, i.e. converges rather than being cut off -- so it is recomputed
    from the evals rather than read.
    """
    runs = BUDGET_RUNS[("0.021", arm)]
    masses = [float(r["ideal_mass"]) for r in runs]
    evals = [int(r["evals"]) for r in runs]

    cap = int(numbers(row[1])[0])
    assert {int(r["eval_cap"]) for r in runs} == {cap}

    spend, percent = (int(n) for n in numbers(row[2])[:2])
    assert round(st.mean(evals)) == spend
    assert round(spend / cap * 100) == percent

    assert f"{st.mean(masses):.5f}" == f"{float(row[3]):.5f}"
    assert f"{st.stdev(masses):.5f}" == f"{float(row[4]):.5f}"  # sample sd, see module docstring
    assert sum(1 for m in masses if m >= BAR) == int(numbers(row[5])[0])


def allocation_rows() -> list[tuple[str, list[str]]]:
    _, rows = _markdown_table(BUDGET, "| arm | allocation |")
    return [(r[0].split("`")[1], r) for r in rows]


ALLOCATION_ROWS = allocation_rows()


@pytest.mark.parametrize("arm,row", ALLOCATION_ROWS, ids=[a for a, _ in ALLOCATION_ROWS])
def test_allocation_table_row(arm, row):
    """Both α columns and the spend, at a fixed budget where allocation is the variable."""
    for column, alpha in [(2, "0.021"), (3, "0.03")]:
        masses = [float(r["ideal_mass"]) for r in BUDGET_RUNS[(alpha, arm)]]
        assert f"{st.mean(masses):.5f}" == f"{float(row[column].strip('*')):.5f}"

    runs = BUDGET_RUNS[("0.021", arm)]
    spend = st.mean(int(r["evals"]) for r in runs) / next(int(r["eval_cap"]) for r in runs)
    assert round(spend * 100) == int(numbers(row[4])[0])


def test_shallow_restarts_beat_deep_ones_by_the_stated_margin():
    """"50 shallow restarts beat 2 deep ones by 40%" -- the study's own conclusion."""
    percent = int(re.search(r"shallow restarts beat few deep ones by \*\*(\d+)%\*\*", BUDGET_FLAT).group(1))
    shallow = st.mean(float(r["ideal_mass"]) for r in BUDGET_RUNS[("0.021", "s50_m200")])
    deep = st.mean(float(r["ideal_mass"]) for r in BUDGET_RUNS[("0.021", "s2_m5000")])
    assert round((shallow / deep - 1) * 100) == percent


def test_no_budget_arm_reaches_the_bar():
    """The study is CONFIRMED-CLOSED: no arm at any budget tested clears 0.078125."""
    for (alpha, arm), runs in BUDGET_RUNS.items():
        mean = st.mean(float(r["ideal_mass"]) for r in runs)
        assert mean < BAR, f"{arm} at α={alpha} reaches the bar"
