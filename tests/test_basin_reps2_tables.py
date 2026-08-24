"""`docs/results/basin-structure-reps2.md`, pinned to its own sweep.

Same treatment as every other write-up in `docs/results/`, and this one earns it
twice over: it reports a **falsified** registered prediction, and a falsification is
only worth anything if the number that produced it stays put.

Two artifacts back it. `basin_study_reps2.json` holds the per-α analysis the script
computed; `basin_study_reps2.csv` holds all 400 tunings, and the document's sharpest
claims -- the clearing tuning's rank by `<H>`, the selection rule's shortfall, the
`<H>`/mass correlation -- are recomputed from those rows rather than read from the
summary, because they are what the conclusion turns on.
"""

from __future__ import annotations

import csv
import json
import re
import statistics as st
from pathlib import Path

import pytest

from _markdown import MINUS, flatten, markdown_table as _markdown_table, numbers

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "results" / "basin-structure-reps2.md"
PLAN = ROOT / "docs" / "plans" / "basin-structure-reps2.md"
DATA = ROOT / "docs" / "results" / "basin_study_reps2.json"
RUNS = ROOT / "docs" / "results" / "basin_study_reps2.csv"

TEXT = DOC.read_text()
FLAT = flatten(TEXT)
#: The document sets a real minus sign; Python formats a hyphen.
FLAT_ASCII = FLAT.replace(MINUS, "-")
STUDY = json.loads(DATA.read_text())
BY_ALPHA = {r["alpha"]: r for r in STUDY["by_alpha"]}
ALPHA_STAR = STUDY["alpha_star"]
BAR = STUDY["bar"]

with RUNS.open() as _handle:
    ROWS = list(csv.DictReader(_handle))

STAR_RUNS = [r for r in ROWS if float(r["alpha"]) == ALPHA_STAR]
STAR_MASS = [float(r["ideal_opt_mass"]) for r in STAR_RUNS]
STAR_H = [float(r["achieved_H"]) for r in STAR_RUNS]


def markdown_table(header_contains: str):
    return _markdown_table(TEXT, header_contains)


def test_the_bar_is_the_pre_registered_one():
    """5 x uniform at m=6, exactly, and unchanged from the plan."""
    assert BAR == 5 / 2**6
    assert f"`5 / 2**6` = **{BAR}**" in FLAT
    assert str(BAR) in PLAN.read_text(), "the bar must be the one registered"


def test_the_run_was_registered_before_it_ran():
    """The document names the plan commit the script verified before sweeping.

    This is the property that makes a falsified prediction a result rather than a
    story, so it is checked rather than trusted: the commit named in the write-up must
    be the one recorded in the artifact, and the plan must exist.
    """
    named = re.search(r"committed at `([0-9a-f]{7,})`", FLAT).group(1)
    assert STUDY["plan_commit"].startswith(named)
    assert PLAN.exists()


def sweep_rows() -> list[tuple[float, list[str]]]:
    _, rows = markdown_table("| α | basins @τ |")
    return [(numbers(r[0])[0], r) for r in rows]


SWEEP_ROWS = sweep_rows()


@pytest.mark.parametrize("alpha,row", SWEEP_ROWS, ids=[f"a{a:g}" for a, _ in SWEEP_ROWS])
def test_sweep_table_row(alpha, row):
    """Every column of the published table against the artifact that produced it."""
    record = BY_ALPHA[alpha]
    assert int(numbers(row[1])[0]) == record["basins_complete_tau"]
    assert int(numbers(row[2])[0]) == record["basins_complete_half"]
    assert int(numbers(row[3])[0]) == record["basins_complete_double"]
    assert int(numbers(row[4])[0]) == record["basins_single_tau"]
    assert f"{numbers(row[5])[0]:.4f}" == f"{record['best_mass']:.4f}"
    assert f"{numbers(row[6])[0]:.4f}" == f"{record['lowest_H_mass']:.4f}"
    assert int(numbers(row[7])[0]) == record["clears_bar"]

    sound = "yes" in row[8] and "no" not in row[8]
    assert sound == record["qubo_min_is_optimum"]
    # A clears count is only meaningful where the encoding is sound; the document
    # says so in prose, and this makes the pairing impossible to break silently.
    if not sound:
        assert "infeasible" in row[8].lower()


def test_the_ladder_matches_the_registered_one():
    """The α ladder is the reps=1 ladder, unchanged, as the plan requires."""
    assert [a for a, _ in SWEEP_ROWS] == sorted(STUDY["alphas"])
    assert ALPHA_STAR in [a for a, _ in SWEEP_ROWS]


def test_both_verdicts_match_the_measurements():
    """P1 held, P2 falsified -- against the artifact, not the prose.

    Deliberately checks the *direction* of each verdict as well as its number. A
    document that quietly flipped "FALSIFIED" to "held" while keeping the figure would
    pass a numbers-only check and would be the worst possible edit here.
    """
    star = BY_ALPHA[ALPHA_STAR]
    p1, p2 = STUDY["verdicts"]["P1_single_basin_does_not_survive"], STUDY["verdicts"]["P2_best_basin_falls_short"]

    assert p1["measured_basins"] == star["basins_complete_tau"]
    assert p1["falsified"] == (star["basins_complete_tau"] == 1)
    assert not p1["falsified"], "P1 held; the document says so"
    assert "**held**" in FLAT

    assert f"{p2['measured_best_mass']:.5f}" == f"{star['best_mass']:.5f}"
    assert p2["falsified"] == (star["best_mass"] >= BAR)
    assert p2["falsified"], "P2 was falsified; the document says so"
    assert "**FALSIFIED**" in TEXT


def test_the_single_basin_regime_is_gone_at_every_rung():
    """"the smallest count anywhere is 11" -- the claim that makes P1 emphatic."""
    smallest = min(r["basins_complete_tau"] for r in STUDY["by_alpha"])
    assert f"smallest count anywhere is **{smallest}**" in FLAT
    assert smallest > 1, "if any rung reaches one basin, P1's framing is wrong"


def test_the_clearing_tuning_and_the_selection_rule():
    """The document's sharpest claim, recomputed from all 40 tunings at α*.

    The clearing tuning is not the one the selection rule returns, and the rule falls
    3.4% short. That gap is the entire conclusion, so every number in it is derived
    here rather than quoted.
    """
    mean, sd = st.mean(STAR_MASS), st.pstdev(STAR_MASS)
    assert f"mean mass **{mean:.5f}**" in FLAT
    assert f"sd {sd:.5f}" in FLAT
    assert f"max **{max(STAR_MASS):.5f}**" in FLAT

    clears = [i for i, m in enumerate(STAR_MASS) if m >= BAR]
    assert len(clears) == 1
    assert f"**{len(clears)} of {len(STAR_MASS)}** clears" in FLAT

    best = max(range(len(STAR_MASS)), key=lambda i: STAR_MASS[i])
    by_h = sorted(range(len(STAR_H)), key=lambda i: STAR_H[i])
    seed = int(STAR_RUNS[best]["tuning_seed"])
    rank = by_h.index(best) + 1
    assert f"seed {seed}" in FLAT
    assert f"**{rank}th of {len(STAR_RUNS)} by `<H>`**" in FLAT

    rule = by_h[0]
    assert int(STAR_RUNS[rule]["tuning_seed"]) == STUDY["reference_tuning_seed"], (
        "the reference is the lowest-<H> tuning, which is the rule under discussion"
    )
    shortfall = (BAR - STAR_MASS[rule]) / BAR * 100
    assert f"mass **{STAR_MASS[rule]:.5f}**" in FLAT
    assert f"**{shortfall:.1f}% short of the bar**" in FLAT
    assert STAR_MASS[rule] < BAR < STAR_MASS[best], (
        "the whole point is that the rule's pick misses and another tuning clears"
    )


def test_the_correlation_is_strong_and_still_fails():
    """"correlation -0.918 -- this is not a broken proxy" -- recomputed.

    The number matters because it forecloses the easy reading. A weak correlation
    would make `<H>` simply a bad proxy; a strong one makes the failure specific to
    the top of the distribution, which is the document's actual claim.
    """
    correlation = st.correlation(STAR_H, STAR_MASS)
    assert f"**{correlation:.3f}**" in FLAT_ASCII
    assert correlation < -0.9, "the document calls this strongly correlated"


def test_the_optimizer_verdict_is_not_reopened():
    """The mean is what an arm is scored on, and it is nowhere near the bar."""
    mean = st.mean(STAR_MASS)
    assert f"mean here is **{mean:.5f}**" in FLAT
    assert mean < BAR
    assert "CONFIRMED-CLOSED" in TEXT


def test_the_trap_row_is_reported_with_its_exactness():
    """α = 0.006 clears 32 of 40 and is infeasible; both halves must be stated."""
    trap = max(
        (r for r in STUDY["by_alpha"] if not r["qubo_min_is_optimum"]),
        key=lambda r: r["clears_bar"],
    )
    assert f"**{trap['clears_bar']} of {len(STAR_MASS)} tunings clear the bar**" in FLAT
    assert f"At α = {trap['alpha']} the QUBO's minimum-energy assignment **is not a" in FLAT


def test_the_usable_window_opens_where_the_sweep_says():
    """The sound region begins at the first exact rung, and the document names it."""
    sound = sorted(r["alpha"] for r in STUDY["by_alpha"] if r["qubo_min_is_optimum"])
    assert f"becomes sound at **{sound[0]}**" in FLAT
    assert sound[0] > 0.010, "the document contrasts this with instance 0's 0.010"
    assert ALPHA_STAR > sound[0], "α* must sit above the lower edge, as claimed"


def test_the_basin_count_had_not_saturated():
    """"grows monotonically with N at every α and never saturates" -- checked.

    This is why the headline count is reported as a lower bound. If it ever does
    saturate, that sentence becomes wrong and the count becomes a measurement.
    """
    for record in STUDY["by_alpha"]:
        counts = [record["basins_by_N"][str(n)] for n in STUDY["report_N"]]
        assert counts == sorted(counts), f"α={record['alpha']} is not monotone in N"

    star = BY_ALPHA[ALPHA_STAR]["basins_by_N"]
    ladder = " → ".join(str(star[str(n)]) for n in STUDY["report_N"])
    assert ladder in FLAT, f"the α* ladder {ladder} is not quoted"
    assert star[str(STUDY["report_N"][-1])] > star[str(STUDY["report_N"][0])]
