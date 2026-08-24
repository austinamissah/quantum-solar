"""The tables in ``docs/results/basin-structure.md``, pinned against `basin_study.json`.

This is the best-backed of the write-ups: every column of its main table is a field
of the committed JSON, so the whole table is compared rather than recomputed. What
is *not* in the JSON is the exactness column -- whether the QUBO's minimizer is the
true optimum at each α -- which the study's figure recomputes at some cost. Here that
column is checked for internal consistency with the regime labels and the usable
window instead, which is what the document actually reasons from.

The study's headline is a **falsified** registered prediction, so the tests are
written to fail if the numbers ever drift back into supporting it: basin count must
be 1 at α* and below, and must rise above.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from _markdown import flatten, markdown_table as _markdown_table, numbers

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "results" / "basin-structure.md"
DATA = ROOT / "docs" / "results" / "basin_study.json"

TEXT = DOC.read_text()
FLAT = flatten(TEXT)
STUDY = json.loads(DATA.read_text())

PRIMARY = str(STUDY["primary_instance"])
RECORDS = {r["alpha"]: r for r in STUDY["by_instance"][PRIMARY]}
ALPHA_STAR = STUDY["alpha_star"]


def markdown_table(header_contains: str):
    return _markdown_table(TEXT, header_contains)


def sensitivity_rows() -> list[tuple[float, list[str]]]:
    _, rows = markdown_table("| α | basins @τ |")
    return [(numbers(r[0])[0], r) for r in rows]


SENSITIVITY_ROWS = sensitivity_rows()


@pytest.mark.parametrize(
    "alpha,row", SENSITIVITY_ROWS, ids=[f"a{a:g}" for a, _ in SENSITIVITY_ROWS]
)
def test_sensitivity_table_row(alpha, row):
    """Every column of the main table is a committed field, so every column is checked.

    Column order is τ, τ/2, 2τ, single-linkage -- note the *table* leads with τ while
    the JSON's names lead with the cutoff, so a column swap here would be easy to make
    and hard to see.
    """
    record = RECORDS[alpha]
    assert int(numbers(row[1])[0]) == record["basins_complete_tau"]
    assert int(numbers(row[2])[0]) == record["basins_complete_half"]
    assert int(numbers(row[3])[0]) == record["basins_complete_double"]
    assert int(numbers(row[4])[0]) == record["basins_single_tau"]
    assert f"{numbers(row[5])[0]:.4f}" == f"{record['tvd_max_pairwise']:.4f}"
    assert f"{numbers(row[6])[0]:.4f}" == f"{record['H_spread']:.4f}"


def test_the_ladder_is_the_registered_one():
    """The α ladder in the table is the one the study committed to, in order."""
    tabled = [a for a, _ in SENSITIVITY_ROWS]
    assert tabled == sorted(tabled), "the ladder must be printed in increasing α"
    assert set(tabled) == set(STUDY["alphas"])


def test_the_falsification_still_reads_as_falsified():
    """One basin at α* and below, rising above: the shape that killed the prediction.

    Written as the property rather than as digits. The registered prediction was a
    U-shape with a strict minimum at α*, and a strict minimum is exactly what this
    asserts is absent -- if the numbers ever drift back to supporting it, this fails
    rather than the document quietly becoming wrong.
    """
    at_or_below = [r["basins_complete_tau"] for a, r in RECORDS.items() if a <= ALPHA_STAR]
    above = [r["basins_complete_tau"] for a, r in sorted(RECORDS.items()) if a > ALPHA_STAR]

    assert set(at_or_below) == {1}, "α* is not a strict minimum: everything below ties it"
    assert above == sorted(above), "basin count must rise monotonically above α*"
    assert min(above) > 1
    assert "FALSIFIED" in TEXT


def test_the_default_weight_basin_count_is_quoted_correctly():
    """"19 distinct basins out of 40 tunings at the default weight, against 1 at α*"."""
    basins, tunings = (
        int(g)
        for g in re.search(r"(\d+) distinct basins out of (\d+) tunings", FLAT).groups()
    )
    assert tunings == STUDY["headline_N"]
    assert basins == RECORDS[max(RECORDS)]["basins_complete_tau"]
    assert RECORDS[ALPHA_STAR]["basins_complete_tau"] == 1


def test_the_cutoff_sensitivity_is_quoted_correctly():
    """"α=1.0: 22 / 19 / 13 at τ/2 / τ / 2τ" -- the order is easy to get backwards."""
    half, tau, double = (
        int(g)
        for g in re.search(r"α=1\.0: (\d+) / (\d+) / (\d+) at τ/2 / τ / 2τ", FLAT).groups()
    )
    record = RECORDS[1.0]
    assert (half, tau, double) == (
        record["basins_complete_half"],
        record["basins_complete_tau"],
        record["basins_complete_double"],
    )


def test_tau_and_the_run_parameters_match_the_study():
    """τ, its sd, and the tuning count, against the JSON that produced them."""
    tau, sd = (
        float(g) for g in re.search(r"\*\*τ = ([\d.]+)\*\* \(sd ([\d.]+)\)", FLAT).groups()
    )
    assert f"{tau:.6f}" == f"{STUDY['tau']:.6f}"
    assert f"{sd:.6f}" == f"{STUDY['tau_sd']:.6f}"

    tunings, alphas, seeds, instances = (
        int(g.replace(",", ""))
        for g in re.search(r"([\d,]+) tunings \((\d+) α × (\d+) seeds × (\d+) instances\)", FLAT).groups()
    )
    assert alphas == len(STUDY["alphas"])
    assert seeds == STUDY["headline_N"]
    assert instances == 1 + len(STUDY["robustness_instances"])
    assert tunings == alphas * seeds * instances


def regime_rows() -> list[tuple[float, list[str]]]:
    _, rows = markdown_table("| QUBO minimizer is the true optimum? |")
    return [(numbers(r[0])[0], r) for r in rows]


REGIME_ROWS = regime_rows()


@pytest.mark.parametrize(
    "alpha,row", REGIME_ROWS, ids=[f"a{a:g}" for a, _ in REGIME_ROWS]
)
def test_regime_table_row(alpha, row):
    """Basin counts must match the main table, and the regime must follow the columns.

    The exactness column is not in the committed JSON, so it is the one thing here
    taken as given -- but the *label* beside it is then forced: infeasible must read
    as wrong, and a single feasible basin as usable.
    """
    assert int(numbers(row[2])[0]) == RECORDS[alpha]["basins_complete_tau"]

    exact = "no" not in row[1].lower()
    regime = row[3].lower()
    if not exact:
        assert "wrong" in regime, "an infeasible minimizer cannot be a usable regime"
    elif RECORDS[alpha]["basins_complete_tau"] == 1:
        assert "usable" in regime
    else:
        assert "usable" not in regime, "more than one basin is not the usable regime"


def test_the_usable_window_is_the_rows_marked_usable():
    """"0.010 ≤ α ≤ 0.021, and α* sits at its upper edge" -- against the table.

    This is the finding that replaced the falsified prediction, so it is worth pinning
    to the rows rather than to itself.
    """
    low, high = (
        float(g)
        for g in re.search(r"usable window on this instance is ([\d.]+) ≤ α ≤ ([\d.]+)", FLAT).groups()
    )
    usable = [a for a, row in REGIME_ROWS if "usable" in row[3].lower()]
    assert min(usable) == low and max(usable) == high
    assert ALPHA_STAR == max(usable), "α* must sit at the upper edge, not inside"

    # "Going 1.4x above it, to a = 0.030, already doubles the basin count."
    factor, above = (
        float(g) for g in re.search(r"Going ([\d.]+)× above it, to α = ([\d.]+)", FLAT).groups()
    )
    assert round(above / ALPHA_STAR, 1) == factor
    assert RECORDS[above]["basins_complete_tau"] >= 2 * RECORDS[ALPHA_STAR]["basins_complete_tau"]


def selection_rows() -> list[tuple[float, list[str]]]:
    _, rows = markdown_table("| α | N=5 |")
    return [(numbers(r[0])[0], r) for r in rows]


SELECTION_ROWS = selection_rows()


@pytest.mark.parametrize(
    "alpha,row", SELECTION_ROWS, ids=[f"a{a:g}" for a, _ in SELECTION_ROWS]
)
def test_selection_stability_table_row(alpha, row):
    """TVD of the lowest-`<H>` selection to the α* reference, at each seed budget."""
    selection = RECORDS[alpha]["lowest_H_selection_by_N"]
    for column, n in enumerate([5, 10, 20, 40], start=1):
        published = numbers(row[column])[0]
        assert f"{published:.3f}" == f"{selection[str(n)]['tvd_to_alpha_star_ref']:.3f}"


def test_the_selection_rule_picks_one_basin_across_seed_budgets():
    """The correction this study forces on `slack-free-encoding.md`, pinned.

    "lowest-`<H>` converges to TVD 0.1488 and stays there from N=10 to N=40". That
    walk-back is load-bearing -- it is why the 2×2's "ill-defined cell" argument was
    withdrawn -- so the property behind it is checked rather than quoted.

    **Two claims, checked separately, because they hold over different ranges.** The
    quoted figure is held exactly over the range the prose names -- N ≥ 20 since the
    2026-08-23 precision fix, the committed selection being 0.1477 at N=10 against
    0.1488 at N=20 and N=40. The *basin* is the same across every reported budget
    including N=5, which is the weaker claim the table's parenthetical makes: "the
    winning *seed* changes; the selected *basin* does not."

    Both are pinned. Checking only the figure would let the basin claim rot; checking
    only the basin would let the range slide back to N=10, which is the error this
    fix corrected.
    """
    settled, low, high = (
        re.search(r"converges to TVD ([\d.]+) and stays there from N=(\d+) to N=(\d+)", FLAT).groups()
    )
    selection = RECORDS[max(RECORDS)]["lowest_H_selection_by_N"]
    quoted = [n for n in STUDY["report_N"] if int(low) <= n <= int(high)]
    assert quoted, f"no reported seed budget lies in N={low}..{high}"

    for n in quoted:
        assert f"{selection[str(n)]['tvd_to_alpha_star_ref']:.4f}" == f"{float(settled):.4f}", (
            f"N={n} is inside the range the prose names but does not hold its figure"
        )

    # Just below the named range the figure must move, or the range understates itself.
    below = [n for n in STUDY["report_N"] if n < int(low)]
    if below:
        assert any(
            f"{selection[str(n)]['tvd_to_alpha_star_ref']:.4f}" != f"{float(settled):.4f}"
            for n in below
        ), f"the figure is already held below N={low}; the range is too conservative"

    # The basin, however, is one across every reported budget -- the weaker claim.
    for n in STUDY["report_N"]:
        drift = abs(selection[str(n)]["tvd_to_alpha_star_ref"] - float(settled))
        assert drift < STUDY["tau"], (
            f"N={n} selects a different basin: {drift:.4f} away, τ = {STUDY['tau']}"
        )
    assert len({selection[str(n)]["seed"] for n in STUDY["report_N"]}) > 1, (
        "the winning seed is supposed to move; if it does not, the claim is trivial"
    )
