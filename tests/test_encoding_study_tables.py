"""The tables in ``docs/results/slack-free-encoding.md``, pinned.

Like `capacity-rate-sensitivity.md`, this document is hand-written and its numbers
were unchecked. It is harder to gate, because its figures do not all live in one
generated JSON -- they come from the encodings themselves, from a committed CSV, from
hardware runs, and in places from the prose alone. So each table is pinned against
whatever is actually load-bearing for it, and **what cannot honestly be checked is
named** rather than papered over:

* **Qubit counts are recomputed** from the encodings on the real 24-slot instance.
  This is the document's headline (117 → 52) and it is fully derivable, so it is.
* **Dollar losses are recomputed** from the per-kWh/day constant in the sibling
  document, which is the document's own explanation for them, and the percentages
  from the $455.72 baseline in that document's JSON.
* **Optimizer arm results are recomputed** from ``optimizer_pairs.csv`` -- but that
  CSV holds only the robustness instances. The **primary instance is not committed**,
  so its rows are skipped with a reason rather than silently passing, and the two
  tables that both quote it are checked against *each other* instead.
* **Gate counts are read, never re-transpiled.** Transpilation is not deterministic
  across calls -- one circuit compiled to 113 vs 98 two-qubit gates on consecutive
  runs (`docs/LESSONS.md` §6) -- so a test that re-transpiled would be flaky and
  would also be testing the wrong thing. Only the arithmetic *over* those counts is
  checked: the depolarizing model's ε column and the reduction percentages.
* **The landscape band table is not reproducible here** (500,000 parameter vectors
  per α, uncommitted), so only its internal structure is checked: nested bands, band
  sizes as fractions of n, and the monotonicity the surrounding prose claims.

Ratio claims get an interval check rather than an equality one. Where a document
states a ratio computed from unrounded values and prints the rounded inputs beside
it -- "0.00013 → 0.0453 (349×)", where the printed quotient is 348 -- demanding
equality would fail on correct arithmetic. See ``rounding_interval``.
"""

from __future__ import annotations

import csv
import json
import math
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest

from _markdown import (
    flatten,
    markdown_table as _markdown_table,
    numbers,
    rounding_interval,
    signed_float,
    to_the_cent,
)

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "results" / "slack-free-encoding.md"
SIBLING = ROOT / "docs" / "results" / "capacity-rate-sensitivity.md"
SIBLING_DATA = ROOT / "docs" / "results" / "capacity_rate_sensitivity.json"
PAIRS = ROOT / "docs" / "results" / "optimizer_pairs.csv"
SNAPSHOT = ROOT / "docs" / "figures" / "web" / "schedule_real_day.json"

TEXT = DOC.read_text()
FLAT = flatten(TEXT)


def markdown_table(header_contains: str):
    """This document's table by a fragment of its header."""
    return _markdown_table(TEXT, header_contains)


# --- the annual dollars table ----------------------------------------------------

#: The battery's full annual value, from the sibling study's generated JSON.
BASELINE = json.loads(SIBLING_DATA.read_text())["annual"]["battery_savings_lossless"]

#: The per-kWh/day constant, taken from the sibling document that derives it. This
#: document asserts the two are the same figure; reading it from there is what makes
#: that assertion testable rather than restated.
CONSTANT = float(
    re.search(r"\$(\d+\.\d{4}) /yr per kWh/day", flatten(SIBLING.read_text())).group(1)
)


def real_instance():
    """The 24-slot Golden CO instance the annual table is computed on."""
    from quantum_solar import BatteryProblem

    snap = json.loads(SNAPSHOT.read_text())
    bucket = snap["buckets"]["summer_weekday"]
    return BatteryProblem(
        generation=np.array(bucket["generation"], dtype=float),
        load=np.array(bucket["load"], dtype=float),
        price=np.array(bucket["price"], dtype=float),
        capacity=float(snap["capacity"]),
        charge_energy=float(snap["charge_energy"]),
        discharge_energy=float(snap["charge_energy"]),
        initial_soc=float(bucket["initial_soc"]),
    )


def encodings_by_name():
    """The encoding each row of the annual table names.

    ``none`` has no entry: it is the row where the SoC constraint is dropped
    altogether, which is why its bill is invalid rather than merely worse.
    """
    from quantum_solar.encodings import Encoding

    return {
        "exact": Encoding.EXACT,
        "cp5band": Encoding.checkpoint(5, banded=True),
        "cp5": Encoding.checkpoint(5),
        "cp3band": Encoding.checkpoint(3, banded=True),
        "cp3": Encoding.checkpoint(3),
    }


def annual_rows() -> list[tuple[str, list[str]]]:
    _, rows = markdown_table("| encoding |")
    return [(r[0].strip("*"), r) for r in rows]


ANNUAL_ROWS = annual_rows()


@pytest.mark.parametrize("name,row", ANNUAL_ROWS, ids=[n for n, _ in ANNUAL_ROWS])
def test_annual_table_qubit_count(name, row):
    """The qubit column, recomputed from the encodings on the real instance.

    This is the document's headline claim -- full battery value at 52 qubits against
    the exact encoding's 117 -- and it is derivable, so nothing here is transcribed.
    """
    problem = real_instance()
    decision_bits = 2 * len(problem.price)
    published = int(numbers(row[1])[0])

    if name == "none":
        assert published == decision_bits, "the unconstrained row is decision bits only"
        return
    encoding = encodings_by_name()[name]
    assert published == decision_bits + encoding.aux_bits(problem)


@pytest.mark.parametrize("name,row", ANNUAL_ROWS, ids=[n for n, _ in ANNUAL_ROWS])
def test_annual_table_loss_columns(name, row):
    """Lost dollars against the constant, and lost percent against the baseline.

    The percentage has no independent source, so it is recomputed from the dollars
    printed beside it -- the two columns cannot disagree without failing here.
    """
    lost, percent = signed_float(row[2]), signed_float(row[3])

    if name == "none":
        # This row reports no loss at all: with the constraint dropped the bill is
        # not a worse bill, it is not a bill. Printing 0.00 here would be a lie.
        assert lost is None and percent is None, "the invalid row must print dashes"
        assert int(numbers(row[4])[0]) <= 365, "infeasible days cannot exceed the year"
        return

    assert percent is not None
    assert to_the_cent(percent) == to_the_cent(lost / BASELINE * 100)

    # Every loss is a whole number of kWh/day of peak throughput at the constant.
    steps = lost / CONSTANT
    assert to_the_cent(lost) == to_the_cent(round(steps) * CONSTANT), (
        f"{name} loses ${lost}, which is not a whole multiple of ${CONSTANT}/kWh/day"
    )


def test_the_cross_document_identity_is_stated_and_holds():
    """$113.93 here and in the sibling document is one figure, not a transcription.

    The document says so at length; the property that makes it true is that both are
    two kWh/day of the same constant. A reader "fixing" one of the two is the edit
    this catches, exactly as in the sibling document's multiplier table.
    """
    assert "not** a transcription between the two documents" in FLAT
    shared = to_the_cent(2 * CONSTANT)
    assert f"${shared}" in FLAT
    assert f"${shared}" in flatten(SIBLING.read_text())


def test_the_free_encodings_are_the_ones_the_headline_names():
    """Rows costing nothing must print zero in both loss columns, and be claimed."""
    free = [n for n, row in ANNUAL_ROWS if signed_float(row[2]) == 0.0]
    for name, row in ANNUAL_ROWS:
        if name in free:
            assert signed_float(row[3]) == 0.0, f"{name} loses % but not $"
    assert "cp5band" in free and "exact" in free


# --- penalty scaling and the concentration bar -----------------------------------


def test_the_bar_is_five_times_uniform():
    """0.078125 is exactly 5/2**6, not a rounded quantity.

    The bar is pre-registered, so it must not drift; being an exact dyadic rational
    is what lets this be an equality rather than a tolerance.
    """
    qubits = int(re.search(r"5 × uniform at m=(\d+)", FLAT).group(1))
    bar = float(re.search(r"required \*\*([\d.]+)\*\*", FLAT).group(1))
    assert bar == 5 / 2**qubits


def test_alpha_star_is_span_over_penalty():
    """α* = (objective span) / (default penalty), from the document's own numbers.

    Checked through the rounding interval of the two printed inputs: they are quoted
    to four and two significant figures respectively, so the quotient is only pinned
    to the precision they carry.
    """
    span = re.search(r"objective span of \*\*([\d.]+)\*\*", FLAT).group(1)
    penalty = re.search(r"penalty scale of ([\d.]+) against", FLAT).group(1)
    alpha = re.search(r"\(objective span\) / \(default penalty\) = ([\d.]+)", FLAT).group(1)

    lo_span, hi_span = rounding_interval(span)
    lo_pen, hi_pen = rounding_interval(penalty)
    lo_alpha, hi_alpha = rounding_interval(alpha)
    assert lo_alpha <= lo_span / hi_pen and hi_span / lo_pen <= hi_alpha

    overshoot = int(re.search(r"a \*\*(\d+)×\*\* overshoot", FLAT).group(1))
    assert round(float(penalty) / float(span)) == overshoot


def test_the_expectation_progress_percentage():
    """"96.6% of the way from the uniform value to the QUBO minimum" -- recomputed."""
    reached, percent, uniform, minimum = (
        float(g)
        for g in re.search(
            r"reached `<H>` = ([\d.]+) \((\d+\.\d)% of the way from the "
            r"uniform-superposition value of ([\d.]+) to the QUBO minimum of "
            r"([\d.]+)\)",
            FLAT,
        ).groups()
    )
    assert f"{(uniform - reached) / (uniform - minimum) * 100:.1f}" == f"{percent:.1f}"


def assert_ratio_is_consistent(small: str, large: str, ratio: str) -> None:
    """The stated ratio must lie in the range its own printed endpoints allow.

    Equality against the naive quotient would be wrong: these ratios are computed
    from unrounded masses, so 0.0453/0.00013 is published as 349× while the printed
    figures divide to 348. The interval the inputs describe is the honest bound.
    """
    lo_small, hi_small = rounding_interval(small)
    lo_large, hi_large = rounding_interval(large)
    assert lo_large / hi_small <= float(ratio) <= hi_large / lo_small, (
        f"{large}/{small} cannot be {ratio}x at the precision printed"
    )


@pytest.mark.parametrize(
    "pattern,label",
    [
        (r"ideal mass \*\*(\d+)×\*\* \(([\d.]+) → ([\d.]+)\)", "440x-rescaling"),
        (r"([\d.]+) to \*\*([\d.]+) \((\d+)×\)\*\*", "349x-like-for-like"),
    ],
    ids=lambda v: v if isinstance(v, str) and "x" in v else "",
)
def test_stated_ratios_are_consistent_with_their_printed_endpoints(pattern, label):
    """Each "N×" is consistent with the two masses printed beside it."""
    match = re.search(pattern, FLAT)
    assert match is not None, f"claim has been reworded: {pattern}"

    groups = list(match.groups())
    ratio = next(g for g in groups if "." not in g)
    endpoints = sorted((g for g in groups if "." in g), key=float)
    assert len(endpoints) == 2, f"expected two endpoints in {groups}"
    assert_ratio_is_consistent(endpoints[0], endpoints[1], ratio)


@pytest.mark.parametrize("alpha", ["0.0209", "0.021"])
def test_the_alpha_sensitive_ratios_share_one_baseline(alpha):
    """"α=0.0209 gives 0.08839 (465×)" -- against the 0.00019 endpoint stated once.

    These two claims print only their own mass, taking the baseline from the sentence
    above them. That shared baseline is what makes them comparable, so it is read
    from the document rather than repeated per claim.
    """
    baseline = re.search(r"the `([\d.]+)` endpoint reproduces exactly", FLAT).group(1)
    mass, ratio = re.search(rf"α={alpha} gives ([\d.]+) \((\d+)×\)", FLAT).groups()
    assert_ratio_is_consistent(baseline, mass, ratio)


# --- the optimizer arm tables ----------------------------------------------------

BAR = 5 / 2**6


def pair_runs() -> dict[tuple[str, str, str], list[float]]:
    """``optimizer_pairs.csv`` grouped by (instance, α, arm)."""
    grouped = defaultdict(list)
    with PAIRS.open() as handle:
        for row in csv.DictReader(handle):
            key = (row["instance_seed"], f"{float(row['alpha']):g}", row["arm"])
            grouped[key].append(float(row["ideal_mass"]))
    return grouped


RUNS = pair_runs()
COMMITTED_INSTANCES = {inst for inst, _, _ in RUNS}


def instance_rows() -> list[tuple[str, str, list[str]]]:
    _, rows = markdown_table("| instance |")
    return [(r[0].split()[0], f"{numbers(r[1])[0]:g}", r) for r in rows]


INSTANCE_ROWS = instance_rows()


@pytest.mark.parametrize(
    "instance,alpha,row",
    INSTANCE_ROWS,
    ids=[f"i{i}-a{a}" for i, a, _ in INSTANCE_ROWS],
)
def test_instance_dependence_table_row(instance, alpha, row):
    """Each row's mean and clear count, recomputed from the committed runs.

    The "best arm" column is checked as *a* maximum rather than *the* maximum: the
    document does not state its tie-break, and two arms tie at 7/10 on instance 3.
    Inventing a tie-break here would pin a rule this test cannot know is the one used.
    """
    if instance not in COMMITTED_INSTANCES:
        pytest.skip(
            f"instance {instance} runs are not committed -- optimizer_pairs.csv holds "
            f"only {sorted(COMMITTED_INSTANCES)}; this row is covered by the "
            f"cross-table check instead"
        )

    arm, mean, clears = row[2], float(row[3]), int(numbers(row[4])[0])
    masses = RUNS[(instance, alpha, arm)]
    assert masses, f"no committed runs for {arm} at instance {instance}, α={alpha}"

    assert f"{st.mean(masses):.5f}" == f"{mean:.5f}"
    assert sum(1 for m in masses if m >= BAR) == clears

    best = max(
        sum(1 for m in v if m >= BAR)
        for (i, a, _), v in RUNS.items()
        if (i, a) == (instance, alpha)
    )
    assert clears == best, f"{arm} is not among the best arms in this cell"

    verdict = row[5].strip("*")
    assert (clears == 0) == (verdict == "fail")
    assert ("RELIABLE" in verdict) == (clears >= 9)


def test_the_two_optimizer_tables_agree_on_the_primary_instance():
    """The primary instance's runs are uncommitted, so the tables check each other.

    Both quote the same arm at the same α. A change to one and not the other is the
    realistic drift here, and it is the only handle available without the CSV.
    """
    _, arm_rows = markdown_table("| arm |")
    arms = {r[0]: (float(r[1]), float(r[2])) for r in arm_rows}

    primary = [(a, r) for i, a, r in INSTANCE_ROWS if i not in COMMITTED_INSTANCES]
    assert primary, "expected the primary instance to be absent from the CSV"

    for alpha, row in primary:
        arm, mean = row[2], float(row[3])
        assert arm in arms, f"{arm!r} is not in the arm table"
        column = arms[arm][0 if alpha == "0.021" else 1]
        assert f"{column:.5f}" == f"{mean:.5f}", (
            f"the two tables disagree on {arm} at α={alpha}"
        )


def test_no_arm_reaches_the_bar_on_the_primary_instance():
    """The section's claim: every arm × α combination fails on the primary."""
    _, arm_rows = markdown_table("| arm |")
    for row in arm_rows:
        for mean in (float(row[1]), float(row[2])):
            assert mean < BAR, f"{row[0]} reaches the bar, contradicting the section"

    stated = int(re.search(r"\*\*all (\d+) arm × α combinations fail", FLAT).group(1))
    assert stated == 2 * len(arm_rows)


def test_transfer_is_near_deterministic():
    """"`transfer` is near-deterministic (sd 0.00014)" and its instance-3 sd.

    Both are population standard deviations; computing the sample one instead gives
    0.00107 against a published 0.00102, which is the kind of near-miss that reads as
    a transcription error and is not one.
    """
    published = float(re.search(r"sd 0\.00102, 10/10", FLAT).group(0).split()[1].rstrip(","))
    masses = RUNS[("3", "0.021", "transfer")]
    assert f"{st.pstdev(masses):.5f}" == f"{published:.5f}"


# --- circuit cost and the transpiler ---------------------------------------------


def circuit_rows() -> list[tuple[str, int, float]]:
    _, rows = markdown_table("| circuit | qubits |")
    return [(r[0].strip("*"), int(numbers(r[3])[0]), float(numbers(r[4])[0])) for r in rows]


CIRCUIT_ROWS = circuit_rows()


@pytest.mark.parametrize(
    "name,gates_o3,epsilon",
    CIRCUIT_ROWS,
    ids=[n.split()[0] for n, _, _ in CIRCUIT_ROWS],
)
def test_epsilon_follows_the_depolarizing_model(name, gates_o3, epsilon):
    """The ε column is the depolarizing model applied to the o3 gate count.

    The gate counts themselves are read, never re-transpiled: transpilation is not
    deterministic across calls (`docs/LESSONS.md` §6), so re-deriving them would make
    this test flaky and would not be checking the document anyway.
    """
    rate = float(re.search(r"~([\d.]+)% effective error per 2-qubit gate", FLAT).group(1))
    predicted = 1 - (1 - rate / 100) ** gates_o3
    assert f"{predicted:.2f}" == f"{epsilon:.2f}"


def transpiler_rows() -> list[tuple[str, int, int, int]]:
    _, rows = markdown_table("| 2Q at o1 (July) |")
    return [
        (r[0], int(numbers(r[1])[0]), int(numbers(r[2])[0]), int(numbers(r[3])[0]))
        for r in rows
    ]


TRANSPILER_ROWS = transpiler_rows()


@pytest.mark.parametrize(
    "name,o1,o3,reduction",
    TRANSPILER_ROWS,
    ids=[n for n, _, _, _ in TRANSPILER_ROWS],
)
def test_transpiler_reduction_percentage(name, o1, o3, reduction):
    """Each reduction is its own row's two gate counts, and level 3 never loses."""
    assert o3 <= o1, "level 3 should not produce more gates than level 1"
    assert round((o1 - o3) / o1 * 100) == reduction


def test_the_headline_reduction_range_is_the_measured_span():
    """"a free 8-18% gate reduction" must be exactly the span of its own table.

    It read 12-18% until 2026-08-23, which was the range over the two T=3 circuits
    rather than over the four this section reports -- the T=2 pair reduces by 11% and
    8%. Now that the heading covers all four rows, both ends can be pinned to the
    table instead of merely bounded by it, which is what catches a row being added or
    re-measured without the heading following.
    """
    low, high = (int(g) for g in re.search(r"a free (\d+)-(\d+)% gate reduction", FLAT).groups())
    measured = [r for _, _, _, r in TRANSPILER_ROWS]
    assert (low, high) == (min(measured), max(measured))


def test_the_script_comment_quotes_the_same_range_as_the_study():
    """The transpiler default is set in code, and its comment repeats this range.

    A comment justifying a live default is a claim like any other; it carried the
    same wrong 12-18% and drifted from the write-up unnoticed because nothing read
    both. This reads both.
    """
    script = (ROOT / "scripts" / "experiment_hardware.py").read_text()
    low, high = (int(g) for g in re.search(r"2-qubit gates (\d+)-(\d+)%", script).groups())
    measured = [r for _, _, _, r in TRANSPILER_ROWS]
    assert (low, high) == (min(measured), max(measured))

    # The comment also lists the gate counts it is derived from; they must be the
    # study's own columns, or the two are describing different circuits.
    before, after = re.search(r"circuits: ([\d/]+) -> ([\d/]+)\)", script).groups()
    assert [int(n) for n in before.split("/")] == [o1 for _, o1, _, _ in TRANSPILER_ROWS]
    assert [int(n) for n in after.split("/")] == [o3 for _, _, o3, _ in TRANSPILER_ROWS]


# --- hardware runs ---------------------------------------------------------------


def test_pooled_hardware_statistics():
    """Mean and t(2) 95% CI, recomputed from the three per-run gaps.

    The interval is the document's actual hardware conclusion, and it is the one
    number here that no other document restates, so it is worth deriving rather than
    trusting.
    """
    from scipy import stats

    _, rows = markdown_table("| run | normalized gap |")
    gaps = [float(numbers(r[1])[0]) for r in rows]
    assert len(gaps) == 3

    mean, low, high = (
        float(g)
        for g in re.search(
            r"Pooled: mean ([\d.]+), t\(\d\) 95% CI \[\+([\d.]+), \+([\d.]+)\]", FLAT
        ).groups()
    )

    assert f"{st.mean(gaps):.4f}" == f"{mean:.4f}"
    half = stats.t.ppf(0.975, len(gaps) - 1) * st.stdev(gaps) / math.sqrt(len(gaps))
    assert f"{st.mean(gaps) - half:.4f}" == f"{low:.4f}"
    assert f"{st.mean(gaps) + half:.4f}" == f"{high:.4f}"
    assert all(g > 0 for g in gaps), "the document says all three runs are positive"


def test_the_variance_gate_ratio():
    """σ_device/gap = 0.389 against a 0.361 threshold, and it does fail it.

    The document reports this as INDETERMINATE with the point estimate on the wrong
    side of the threshold; that is an uncomfortable result to keep stated correctly,
    which is why it is pinned.
    """
    sigma = float(re.search(r"σ_device = ([\d.]+)", FLAT).group(1))
    ratio, threshold = (
        float(g)
        for g in re.search(
            r"σ_device/gap = ([\d.]+) \*fails\* the ([\d.]+) threshold", FLAT
        ).groups()
    )
    _, rows = markdown_table("| run | normalized gap |")
    gaps = [float(numbers(r[1])[0]) for r in rows]

    assert f"{sigma / min(gaps):.3f}" == f"{ratio:.3f}", (
        "the ratio is σ_device over the run it was measured on"
    )
    assert ratio > threshold, "the document says the point estimate fails the gate"


def test_the_weight_sensitivity_table():
    """The 2×2 note's TVD ratios, against the expected floors stated beneath it."""
    _, rows = markdown_table("| encoding | TVD(ideal @default")
    floors = dict(
        zip(
            ["exact", "cp3"],
            [
                float(g)
                for g in re.search(
                    r"= ([\d.]+) \(exact @[\d,]+\) and ([\d.]+) \(cp3 @[\d,]+\)", FLAT
                ).groups()
            ],
        )
    )

    moves = {}
    for row in rows:
        name = row[0].strip("`*")
        tvd, ratio = float(numbers(row[1])[0]), float(numbers(row[2])[0])
        moves[name] = tvd
        assert f"{tvd / floors[name]:.1f}" == f"{ratio:.1f}", name

    # "cp3's circuit moves about 4x less than exact's with the weight."
    stated = int(re.search(r"moves about \*\*(\d+)× less\*\*", FLAT).group(1))
    assert round(moves["exact"] / moves["cp3"]) == stated


def test_the_superseded_ratio_in_the_correction_is_also_arithmetic():
    """The correction states what the wrong figure was and why; both must hold.

    A correction that misstates its own retracted number is worse than no correction,
    and this one is load-bearing -- it is why the 2×2 was declined on one reason
    rather than two.
    """
    old_tvd, old_ratio = (
        float(g)
        for g in re.search(
            r"reported `cp3` at TVD \*\*([\d.]+)\*\* and\s+\*\*([\d.]+)×\*\*", FLAT
        ).groups()
    )
    realized = float(
        re.search(r"a single realized draw \(([\d.]+)\)", FLAT).group(1)
    )
    assert f"{old_tvd / realized:.1f}" == f"{old_ratio:.1f}"


# --- the landscape band table ----------------------------------------------------


def test_landscape_bands_are_internally_consistent():
    """Not reproducible here (500,000 vectors per α, uncommitted), so structure only.

    What is checkable without the samples: each band is the stated fraction of the
    global n, the bands nest, and mean mass rises as they tighten -- which is the
    claim the surrounding prose makes from this table.
    """
    _, rows = markdown_table("| band | n |")
    bands = [r for r in rows if "%" in r[0]]
    global_row = next(r for r in rows if r[0] == "global")
    total = numbers(global_row[1])[0]

    lows, means = [], []
    for row in [global_row] + bands:
        if "%" in row[0]:
            fraction = float(row[0].split("%")[0].split()[-1]) / 100
            assert numbers(row[1])[0] == total * fraction, f"{row[0]} is not {fraction} of n"
        low, high = numbers(row[2])[:2]
        lows.append(low)
        means.append(float(row[4]))
        assert low < high

    assert len(set(lows)) == 1, "every band shares the global minimum as its floor"
    assert means == sorted(means), "mean mass must rise as the band tightens"

    uppers = [numbers(r[2])[1] for r in [global_row] + bands]
    assert uppers == sorted(uppers, reverse=True), "tighter bands must have lower ceilings"
