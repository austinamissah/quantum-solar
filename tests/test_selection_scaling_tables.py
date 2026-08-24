"""`docs/results/selection-rule-scaling.md`, pinned to its own sweep.

The findings are gated, and so are the sentences that limit them. This write-up makes
a claim ("feasible mass picks the argmax at every size") next to a warning that the
margin is small and the stakes are much lower than at T=3. Dropping the warning while
keeping the claim would leave every number correct and the paper overstated, so the
warning is a test.
"""

from __future__ import annotations

import csv
import json
import re
import statistics as st
from pathlib import Path

import pytest

from _markdown import flatten, markdown_table as _markdown_table, numbers

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "results" / "selection-rule-scaling.md"
PLAN = ROOT / "docs" / "plans" / "selection-rule-scaling.md"
DATA = ROOT / "docs" / "results" / "selection_rule_scaling.json"
RUNS = ROOT / "docs" / "results" / "selection_rule_scaling.csv"

TEXT = DOC.read_text()
FLAT = flatten(TEXT)
STUDY = json.loads(DATA.read_text())
BY_SIZE = {r["T"]: r for r in STUDY["by_size"]}

with RUNS.open() as _handle:
    ROWS = list(csv.DictReader(_handle))


def test_the_sweep_was_registered_before_it_ran():
    named = re.search(r"committed at `([0-9a-f]{7,})`", FLAT).group(1)
    assert STUDY["plan_commit"].startswith(named)
    assert PLAN.exists()


def test_both_verdicts_match_the_sweep():
    v = STUDY["verdicts"]
    p1, p2 = v["P1_direct_rule_dies_with_size"], v["P2_feasible_mass_survives"]

    assert p1["falsified"] == (p1["tunings_mostly_identifiable"] >= p1["of"] / 2)
    assert not p1["falsified"]
    assert f"**{p1['tunings_mostly_identifiable']} of {p1['of']}**" in FLAT

    assert p2["falsified"] == (p2["wins"] < p2["losses"])
    assert not p2["falsified"]
    assert f"**{p2['wins']} wins, {p2['losses']} losses**" in FLAT
    assert p2["wins"] + p2["losses"] <= p2["sizes"]


def test_the_escape_clause_did_not_fire_and_the_document_says_so():
    """The plan pre-committed that a size below uniform proves nothing.

    Whether it fired decides if the study means anything, so it is checked rather
    than asserted -- and the document has to state which way it went.
    """
    above = STUDY["informative"]["sizes_with_mass_above_uniform"]
    assert above == [r["T"] for r in STUDY["by_size"]], "some size is at or below uniform"
    assert "did not fire" in FLAT
    assert "escape clause" in FLAT or "escape clause" in PLAN.read_text()


def size_rows():
    _, rows = _markdown_table(TEXT, "| T | qubits | best mass |")
    return [(int(numbers(r[0])[0]), r) for r in rows]


SIZE_ROWS = size_rows()


@pytest.mark.parametrize("slots,row", SIZE_ROWS, ids=[f"T{t}" for t, _ in SIZE_ROWS])
def test_result_table_row(slots, row):
    """Every column against the sweep, including the rank `<H>` gives the best tuning."""
    record = BY_SIZE[slots]
    assert int(numbers(row[1])[0]) == record["qubits"]
    assert f"{numbers(row[2])[0]:.6f}" == f"{record['best_mass']:.6f}"
    assert f"{numbers(row[3])[0]:.1f}" == f"{record['best_mass'] / record['uniform']:.1f}"
    assert f"{numbers(row[4])[0]:.6f}" == f"{record['rules']['feasible_mass']['picked_mass']:.6f}"
    assert f"{numbers(row[5])[0]:.6f}" == f"{record['rules']['lowest_H']['picked_mass']:.6f}"
    assert int(numbers(row[6])[0]) == record["rules"]["lowest_H"]["rank_of_argmax"]


def test_feasible_mass_picks_the_argmax_at_every_size():
    """The headline. Rank 1 everywhere, and `<H>` rank 1 nowhere."""
    ranks = [r["rules"]["feasible_mass"]["rank_of_argmax"] for r in STUDY["by_size"]]
    incumbent = [r["rules"]["lowest_H"]["rank_of_argmax"] for r in STUDY["by_size"]]
    assert set(ranks) == {1}, "the claim is rank 1 at every size"
    assert 1 not in incumbent, "the contrast is that `<H>` picks it at none"
    assert f"rank 1, four for four" in FLAT


def identifiability_rows():
    _, rows = _markdown_table(TEXT, "| T | qubits | mean identifiability |")
    return [(int(numbers(r[0])[0]), r) for r in rows]


IDENT_ROWS = identifiability_rows()


@pytest.mark.parametrize("slots,row", IDENT_ROWS, ids=[f"T{t}" for t, _ in IDENT_ROWS])
def test_identifiability_row(slots, row):
    """The direct rule's precondition, recomputed from the 20 tunings at each size."""
    values = [float(r["identifiable"]) for r in ROWS if int(r["T"]) == slots]
    assert len(values) == BY_SIZE[slots]["n"]
    assert f"{numbers(row[2])[0]:.2f}" == f"{st.mean(values):.2f}"
    assert f"{numbers(row[3])[0]:.2f}" == f"{st.median(values):.2f}"
    assert int(numbers(row[4])[0]) == sum(1 for v in values if v >= 0.5)
    assert f"{numbers(row[5])[0]:.2f}" == f"{max(values):.2f}"


def test_the_direct_rule_is_unreliable_at_the_largest_size():
    """"no tuning at that size on which the direct rule is reliable" -- checked."""
    largest = max(BY_SIZE)
    values = [float(r["identifiable"]) for r in ROWS if int(r["T"]) == largest]
    assert max(values) < 0.7, "if some tuning were reliable, the claim is too strong"
    assert f"manages only **{max(values):.0%}**" in FLAT


def test_the_margin_caveat_survives():
    """The percentages by which `<H>`'s pick is worse, and the warning attached.

    Without this the table reads as `<H>` failing badly. It does not fail badly here;
    it merely never wins, and the document must keep saying so.
    """
    margins = [
        (r["rules"]["feasible_mass"]["picked_mass"] - r["rules"]["lowest_H"]["picked_mass"])
        / r["rules"]["feasible_mass"]["picked_mass"] * 100
        for r in STUDY["by_size"]
    ]
    quoted = ", ".join(f"{m:.1f}%" for m in margins[:-1]) + f" and {margins[-1]:.1f}%"
    assert f"worse by {quoted}" in FLAT
    assert max(margins) < 5, "the document calls these small margins"
    # The numbers alone read as `<H>` failing badly. The sentence that says it does
    # not, and the warning against importing the T=3 stakes, are both load-bearing.
    assert "`<H>` is not catastrophic here" in FLAT
    assert "it simply never picks the best" in FLAT
    assert "Do not quote the T=3 stakes with these ranks" in FLAT


def test_the_non_monotonicity_is_reported_not_smoothed():
    """Concentration is not monotone in T, and the document admits it cannot explain it."""
    ratios = [r["best_mass"] / r["uniform"] for r in STUDY["by_size"]]
    assert ratios != sorted(ratios), "if it became monotone this sentence is wrong"
    quoted = ", ".join(f"{x:.1f}×" for x in ratios)
    assert quoted in FLAT
    assert "cannot explain the shape" in FLAT

    cleared = [r["T"] for r in STUDY["by_size"] if r["any_clears_scaled_bar"]]
    missed = [r["T"] for r in STUDY["by_size"] if not r["any_clears_scaled_bar"]]
    assert cleared and missed, "the document contrasts sizes that clear with ones that do not"
    assert f"T={missed[0]} and T={missed[-1]} do" in FLAT


def test_the_shot_budget_limitation_is_stated():
    """T=7 is still enumerable; this is a shot-budget test, not intractability."""
    largest = BY_SIZE[max(BY_SIZE)]
    assert f"{2 ** largest['qubits']:,} states" in FLAT
    assert "by shot" in FLAT and "not by intractability" in FLAT.replace("**", "")
