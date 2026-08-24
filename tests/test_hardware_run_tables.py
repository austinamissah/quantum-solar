"""The tables in the three ``hardware-run-*.md`` write-ups, pinned.

These report QPU runs that cannot be repeated, so nothing here re-executes anything.
What they *can* be held to is their own arithmetic and their agreement with each
other, and that turns out to cover most of what they claim:

* every ``normalized`` figure is a quotient of two columns printed beside it;
* σ_device is a stated function of two measured spreads;
* the variance gate's cap, ratio and verdict all follow from those;
* the pooled three-run statistics follow from the three per-run gaps -- and those
  three gaps appear in **four** documents, which is checked across all of them.

`tests/test_hardware_circuit_invariance.py` already rebuilds the recorded metrics
from committed angles; this is the layer above that, on what the write-ups say about
those metrics.

**Not covered, deliberately: the implied `k` columns.** They are a depolarizing fit,
and the fit reproduces the published values only to about half a percent -- exact at
`exact @ α=0.021` (0.00424) but 0.00650 against a published 0.00652 for `cp3` r1. The
model as stated in the prose is not enough to pin them, and a test built on a guessed
model would be pinning the guess. The same goes for the ``peak/uniform`` column,
which needs the raw counts rather than anything printed.
"""

from __future__ import annotations

import math
import re
import statistics as st
from pathlib import Path

import pytest
from scipy import stats

from _markdown import (
    assert_quotient,
    flatten,
    markdown_table as _markdown_table,
    numbers,
)

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs" / "results"

ENCODING_RUN = (RESULTS / "hardware-run-encoding.md").read_text()
REPLICATION = (RESULTS / "hardware-run-encoding-replication.md").read_text()
SPREAD = (RESULTS / "hardware-run-spread.md").read_text()
STUDY = (RESULTS / "slack-free-encoding.md").read_text()

SPREAD_FLAT = flatten(SPREAD)
REPLICATION_FLAT = flatten(REPLICATION)
ENCODING_FLAT = flatten(ENCODING_RUN)


# --- hardware-run-encoding.md ----------------------------------------------------


def degradation_rows() -> list[tuple[str, list[str]]]:
    _, rows = _markdown_table(ENCODING_RUN, "| TVD(sim,hw) |")
    return [(r[0].strip("`"), r) for r in rows]


DEGRADATION_ROWS = degradation_rows()


@pytest.mark.parametrize(
    "circuit,row",
    DEGRADATION_ROWS,
    ids=[c.replace(" ", "-") for c, _ in DEGRADATION_ROWS],
)
def test_normalized_degradation_is_the_quotient_of_its_own_columns(circuit, row):
    """``normalized`` = TVD(sim,hw) / TVD(sim,unif), from the same row.

    Normalizing by the distance to uniform is what makes a 6-qubit and a 10-qubit
    circuit comparable, so a row whose normalized figure does not follow from its own
    two columns would break the only comparison the document makes.
    """
    tvd, uniform, normalized = row[5], row[6], row[7].strip("*")
    assert_quotient(tvd, uniform, normalized, circuit)


def test_the_mitigated_rows_pair_with_their_own_circuits():
    """Mitigation changes the hardware term only: the uniform column must not move."""
    uniform = {}
    for circuit, row in DEGRADATION_ROWS:
        base = circuit.replace(" +mitigation", "")
        uniform.setdefault(base, set()).add(row[6])
    for base, values in uniform.items():
        assert len(values) == 1, f"{base} reports two different distances to uniform"


def structure_rows() -> list[tuple[str, list[str]]]:
    _, rows = _markdown_table(ENCODING_RUN, "PR/D")
    return [(r[0].strip("`"), r) for r in rows]


STRUCTURE_ROWS = structure_rows()


@pytest.mark.parametrize(
    "circuit,row", STRUCTURE_ROWS, ids=[c for c, _ in STRUCTURE_ROWS]
)
def test_structure_table_ratios(circuit, row):
    """PR/D and H/ln D, recomputed from the columns beside them.

    D is the dimension, so ln D is the maximum entropy: the normalized entropy column
    is the only thing making the two circuits' spreads comparable at 64 and 1024
    states.
    """
    dimension = numbers(row[1])[0]
    participation, ratio = row[2], row[3].strip("*")
    assert_quotient(participation, f"{dimension:.0f}", ratio, f"{circuit} PR/D")

    entropy, normalized = numbers(row[5])[0], numbers(row[6])[0]
    assert f"{entropy / math.log(dimension):.4f}" == f"{normalized:.4f}"


def test_the_preregistered_band_verdicts_follow_from_the_measurements():
    """INSIDE / OUTSIDE must follow from the measured value and the band.

    The `exact` arm landing *below* its pre-registered band is the run's most
    surprising result; a verdict column that drifted out of step with its own numbers
    would quietly erase it.
    """
    _, rows = _markdown_table(ENCODING_RUN, "| pre-registered band |")
    for row in rows:
        measured = numbers(row[1])[0]
        low, high = numbers(row[2])[:2]
        verdict = row[3].strip("*")
        inside = low <= measured <= high
        assert inside == ("INSIDE" in verdict), row[0]
        if not inside:
            assert ("below" in verdict) == (measured < low), row[0]


def test_the_weight_comparison_table_is_internally_ordered():
    """At the default weight the distribution must be more concentrated, on every column.

    The document's argument is that the default weight collapses the distribution;
    every column of this table has to point the same way for that to hold.
    """
    _, rows = _markdown_table(ENCODING_RUN, "| property | α = 0.021 |")
    values = {r[0]: (numbers(r[1])[0], numbers(r[2])[0]) for r in rows}

    entropy = next(v for k, v in values.items() if "entropy" in k)
    participation = next(v for k, v in values.items() if "participation" in k)
    to_uniform = next(v for k, v in values.items() if "TVD to uniform" in k)
    peak = next(v for k, v in values.items() if "max bitstring" in k)

    assert entropy[0] > entropy[1], "the default weight must lower entropy"
    assert participation[0] > participation[1], "and lower the participation ratio"
    assert to_uniform[0] < to_uniform[1], "and sit further from uniform"
    assert peak[0] < peak[1], "and put more mass on its peak"

    maximum = float(re.search(r"entropy \(nats, max ([\d.]+)\)", ENCODING_FLAT).group(1))
    dimension = participation[0] / float(
        re.search(r"participation ratio \(of (\d+)\)", ENCODING_FLAT).group(1)
    )
    assert 0 < dimension <= 1
    assert f"{math.log(1024):.2f}" == f"{maximum:.2f}"


# --- hardware-run-encoding-replication.md ----------------------------------------


def test_the_replicate_spread_column():
    """spread = |r1 − r2| per arm, and `exact` must be the steadier of the two.

    The document's point is that the two arms are not equally reproducible, so the
    ordering is pinned alongside the arithmetic.
    """
    _, rows = _markdown_table(REPLICATION, "| arm | r1 | r2 | spread |")
    spreads = {}
    for row in rows:
        first, second, spread = row[1], row[2], row[3].strip("*")
        lo, hi = sorted([float(first), float(second)])
        # Both endpoints are rounded, so the difference is only pinned to their span.
        assert abs((hi - lo) - float(spread)) <= 1e-4, row[0]
        spreads[row[0].strip("`")] = float(spread)

    exact = next(v for k, v in spreads.items() if k.startswith("exact"))
    cp3 = next(v for k, v in spreads.items() if k.startswith("cp3"))
    assert exact < cp3, "the document reports `exact` as the more reproducible arm"


def test_the_relative_sd_table_is_the_chi_square_rule():
    """"relative sd of the estimate" = 1/√(2·df), and df = replicates − 1.

    This table is why the run was not read as precise: at two replicates the spread
    estimate carries 71% relative error. It is pure arithmetic and worth holding.
    """
    _, rows = _markdown_table(REPLICATION, "| replicates | df |")
    for row in rows:
        replicates, degrees, relative = (numbers(cell)[0] for cell in row[:3])
        assert degrees == replicates - 1
        assert round(1 / math.sqrt(2 * degrees) * 100) == relative


def test_the_drift_versus_weight_decomposition():
    """The k-asymmetry split: the two terms must sum to the total and to 100%.

    A decomposition whose shares do not sum is the classic way an attribution goes
    wrong, and this one is quoted in `slack-free-encoding.md` as 43/57.
    """
    _, rows = _markdown_table(REPLICATION, "| term | comparison |")
    terms = {r[0].strip("*").lower(): (numbers(r[2])[0], numbers(r[3])[0]) for r in rows}

    total_delta, total_share = terms["total"]
    parts = [v for k, v in terms.items() if k != "total"]

    assert f"{sum(d for d, _ in parts):.5f}" == f"{total_delta:.5f}"
    assert sum(s for _, s in parts) == total_share == 100
    for delta, share in parts:
        assert round(delta / total_delta * 100) == share

    assert f"{int(total_share)}%" in flatten(STUDY) or "43% device drift" in flatten(STUDY)


# --- hardware-run-spread.md ------------------------------------------------------


def spread_value(label: str) -> float:
    """A row of one of the spread document's two-column quantity tables."""
    for line in SPREAD.splitlines():
        if line.startswith("|") and label in line:
            return numbers(line.strip("|").split("|")[1])[0]
    raise AssertionError(f"no row containing {label!r}")


def test_sigma_device_is_the_stated_difference_of_squares():
    """σ_device = √(σ_total² − σ_shot²), the whole basis of the variance gate.

    Recomputed rather than compared: this figure is what the pre-registered gate is
    evaluated against, and it is quoted in two other documents.
    """
    total = spread_value("σ_total")
    shot = spread_value("σ_shot")
    device = spread_value("σ_device = ")
    assert f"{math.sqrt(total**2 - shot**2):.5f}" == f"{device:.5f}"
    assert shot < total, "the shot floor cannot exceed the total spread"


def test_the_variance_gate_table():
    """Cap, point ratio and verdict, for both denominators the document reports.

    The awkward part is pinned on purpose: the point estimate *fails* on this run's
    own gap and only the interval width keeps INDETERMINATE from being FAIL.
    """
    device = spread_value("σ_device = ")
    threshold = float(re.search(r"cap = ([\d.]+) × gap", SPREAD_FLAT).group(1))

    _, rows = _markdown_table(SPREAD, "| denominator | gap |")
    for row in rows:
        gap, cap, ratio = numbers(row[1])[0], numbers(row[2])[0], numbers(row[3])[0]
        assert f"{threshold * gap:.5f}" == f"{cap:.5f}", row[0]
        assert f"{device / gap:.3f}" == f"{ratio:.3f}", row[0]
        assert ("fails" in row[3]) == (ratio > threshold), row[0]
        assert "INDETERMINATE" in row[4]


def run_gaps() -> list[float]:
    """The three per-run normalized gaps, from the spread document's own table."""
    _, rows = _markdown_table(SPREAD, "| run | gap |")
    return [numbers(r[1])[0] for r in rows]


def test_the_three_run_table_agrees_with_its_own_intervals():
    """Each run's device-widened interval must be wider than its shot-only one.

    And run 3 is the one that stops excluding zero once the device term is included,
    which is the qualification the document leads with.
    """
    _, rows = _markdown_table(SPREAD, "| run | gap |")
    for row in rows:
        shot_low, shot_high = numbers(row[2])[:2]
        both_low, both_high = numbers(row[3])[:2]
        if row[3].count("−") or row[3].count("-"):
            both_low = -abs(both_low)
        assert both_high - both_low > shot_high - shot_low, f"run {row[0]}"
        assert (both_low > 0) == (row[4].strip("*") == "yes"), f"run {row[0]}"


def test_the_pooled_summary_follows_from_the_three_gaps():
    """Mean, between-run sd, t(2) interval and the sign test, all recomputed."""
    gaps = run_gaps()
    assert len(gaps) == 3

    _, all_rows = _markdown_table(SPREAD, "| | |")
    values = {r[0].strip("*").lower(): r[1] for r in all_rows}

    assert f"{st.mean(gaps):.4f}" == f"{numbers(values['mean gap'])[0]:.4f}"
    assert abs(st.stdev(gaps) - numbers(values["between-run sd"])[0]) < 1e-5

    low, high = numbers(values["t(2) 95% ci"])[:2]
    half = stats.t.ppf(0.975, len(gaps) - 1) * st.stdev(gaps) / math.sqrt(len(gaps))
    assert f"{st.mean(gaps) - half:.4f}" == f"{low:.4f}"
    assert f"{st.mean(gaps) + half:.4f}" == f"{high:.4f}"

    # "all three positive: yes (sign test p = 0.25)" -- two-sided, 2 * 0.5**3.
    probability = numbers(values["all three positive"])[0]
    assert all(g > 0 for g in gaps)
    assert f"{2 * 0.5 ** len(gaps):.2f}" == f"{probability:.2f}"


def test_the_three_gaps_agree_across_every_document_that_quotes_them():
    """The same three runs are tabled in four write-ups; they must not diverge.

    This is the check that no single document can make on its own, and the one most
    likely to catch a real edit: a gap corrected in one place and not the others.
    """
    gaps = run_gaps()

    _, pooled = _markdown_table(STUDY, "| run | normalized gap |")
    assert [numbers(r[1])[0] for r in pooled] == gaps

    # The replication and first-run documents each report one of the three.
    _, prior = _markdown_table(REPLICATION, "| | median | 95% CI |")
    reported = {numbers(r[1])[0] for r in prior}
    assert reported <= set(gaps), f"{reported} is not a subset of the pooled gaps"

    _, first = _markdown_table(ENCODING_RUN, "| quantity | median |")
    normalized = next(numbers(r[1])[0] for r in first if "normalized" in r[0])
    assert normalized in gaps
