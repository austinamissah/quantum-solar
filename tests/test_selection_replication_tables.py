"""`docs/results/selection-rule-replication.md`, pinned to its own sweep.

The findings and the sentences that bound them are both gated. This write-up removes
the previous study's main caveat, which makes it exactly the kind of document where an
overstatement would be costly -- so the limits it places on itself (P3's three cells
come from one instance; hard instances are 2 of 6 seeds; the tightest margin is
0.00062) are tests, not prose.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from _markdown import flatten, markdown_table as _markdown_table, numbers

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "results" / "selection-rule-replication.md"
PLAN = ROOT / "docs" / "plans" / "selection-rule-replication.md"
DATA = ROOT / "docs" / "results" / "selection_rule_replication.json"

TEXT = DOC.read_text()
FLAT = flatten(TEXT)
STUDY = json.loads(DATA.read_text())
BAR = STUDY["bar"]
BAND = [c for c in STUDY["cells"] if c["sound"] and c["in_band"]]


def outcome_matches(cell: str, falsified: bool) -> bool:
    """The outcome column must say what the flag says.

    Checking the measured column alone let a verdict be flipped to FALSIFIED with
    every figure intact -- found by mutation, and the reason this helper exists.
    """
    said = cell.strip().strip("*").lower()
    return said == ("falsified" if falsified else "held")


def test_the_sweeps_were_registered_first():
    named = re.search(r"committed at `([0-9a-f]{7,})`", FLAT).group(1)
    assert STUDY["plan_commit"].startswith(named)
    assert PLAN.exists()


def test_the_instances_are_fresh():
    """Seeds never used before; the whole point of a replication."""
    used_before = {1, 2, 3}
    assert not (set(STUDY["fresh_instances"]) & used_before)
    assert {c["instance"] for c in STUDY["cells"]} == set(STUDY["fresh_instances"])


def test_all_three_verdicts_match_the_evaluation():
    v = STUDY["verdicts"]
    _, rows = _markdown_table(TEXT, "| | prediction | measured | outcome |")

    p1 = v["P1_argmax_replicates"]
    assert p1["argmax_cells"] == sum(
        1 for c in BAND if c["rules"]["feasible_mass"]["picked_is_argmax"])
    assert p1["of"] == len(BAND)
    assert p1["falsified"] == (p1["fraction"] < p1["floor"])
    assert not p1["falsified"]
    row = next(r for r in rows if "P1" in r[0])
    assert f"**{p1['argmax_cells']} of {p1['of']} ({p1['fraction']:.0%})**" in row[2]
    assert outcome_matches(row[3], p1["falsified"])

    p2 = v["P2_beats_the_incumbent"]
    assert p2["falsified"] == (p2["losses"] >= p2["wins"])
    assert not p2["falsified"]
    row = next(r for r in rows if "P2" in r[0])
    assert f"**{p2['wins']} wins, {p2['losses']} losses**" in row[2]
    assert outcome_matches(row[3], p2["falsified"])

    p3 = v["P3_discriminating_cells"]
    assert p3["estimable"] == bool(p3["stratum_size"])
    assert p3["falsified"] == (p3["estimable"] and
                               p3["feasible_mass_clears"] <= p3["stratum_size"] / 2)
    assert not p3["falsified"]
    row = next(r for r in rows if "P3" in r[0])
    assert f"**{p3['feasible_mass_clears']} of {p3['stratum_size']}**" in row[2]
    assert outcome_matches(row[3], p3["falsified"])


def test_P3_was_estimable_which_the_plan_said_it_might_not_be():
    """The plan registered "not estimable" as a real outcome. It did not happen."""
    p3 = STUDY["verdicts"]["P3_discriminating_cells"]
    assert p3["estimable"] and p3["note"] is None
    assert "the plan expected it might be empty" in FLAT
    assert "It is not." in TEXT


def instance_rows():
    _, rows = _markdown_table(TEXT, "| instance | band cells |")
    return [(int(numbers(r[0])[0]), r) for r in rows]


@pytest.mark.parametrize("instance,row", instance_rows(), ids=lambda v: f"i{v}" if isinstance(v, int) else "")
def test_per_instance_row(instance, row):
    """Band size, mass range, and how often `<H>` misses -- the easy/hard split."""
    cells = [c for c in BAND if c["instance"] == instance]
    assert int(numbers(row[1])[0]) == len(cells)
    lo, hi = numbers(row[2])[:2]
    assert f"{lo:.4f}" == f"{min(c['best_mass'] for c in cells):.4f}"
    assert f"{hi:.4f}" == f"{max(c['best_mass'] for c in cells):.4f}"
    misses = sum(1 for c in cells if not c["rules"]["lowest_H"]["picked_clears"])
    assert int(numbers(row[3])[0]) == misses


def test_the_discriminating_stratum_table():
    """Every figure in the table that carries the result."""
    stratum = [c for c in BAND
               if c["any_clears"] and not c["rules"]["lowest_H"]["picked_clears"]]
    _, rows = _markdown_table(TEXT, "| cell | `<H>` picks |")
    assert len(rows) == len(stratum) == STUDY["verdicts"]["P3_discriminating_cells"]["stratum_size"]

    for cell, row in zip(sorted(stratum, key=lambda c: c["alpha"]), rows):
        h = cell["rules"]["lowest_H"]["picked_mass"]
        f = cell["rules"]["feasible_mass"]["picked_mass"]
        assert f"{numbers(row[1])[0]:.5f}" == f"{h:.5f}"
        assert f"{numbers(row[2])[0]:.5f}" == f"{BAR - h:.5f}"
        assert f"{numbers(row[3])[0]:.5f}" == f"{f:.5f}"
        assert f"{numbers(row[4])[0]:.5f}" == f"{f - BAR:.5f}"
        assert h < BAR <= f, "the stratum is defined by <H> missing and feasible clearing"


def test_the_stratum_is_one_instance_and_the_document_says_so():
    """Three cells, one instance. Counting them as three tests would overstate it."""
    stratum = [c for c in BAND
               if c["any_clears"] and not c["rules"]["lowest_H"]["picked_clears"]]
    assert len({c["instance"] for c in stratum}) == 1
    assert "all come from one instance" in FLAT
    assert "roughly one\n  independent observation" in TEXT


def test_the_hard_instance_rate_is_reported():
    """"two of six seeds are hard" -- the cost of finding a discriminating case."""
    hard = {c["instance"] for c in BAND if not c["rules"]["lowest_H"]["picked_clears"]}
    assert len(hard) == 1, "instance 6 is the only hard one among the fresh three"
    assert "**two** are hard" in FLAT and "instance 1 and instance 6" in FLAT


def test_the_tightest_margin_caveat_survives():
    """The smallest clearance is 0.00062 and would not survive a shot budget."""
    stratum = [c for c in BAND
               if c["any_clears"] and not c["rules"]["lowest_H"]["picked_clears"]]
    tightest = min(c["rules"]["feasible_mass"]["picked_mass"] - BAR for c in stratum)
    assert f"by **{tightest:.5f}**" in FLAT
    assert "not a\n  margin that would survive a modest shot budget" in TEXT


def test_the_margin_summary():
    """Median margin over `<H>`, and the warning against quoting it alone."""
    margins = sorted(
        (c["rules"]["feasible_mass"]["picked_mass"] - c["rules"]["lowest_H"]["picked_mass"])
        / c["rules"]["feasible_mass"]["picked_mass"] * 100 for c in BAND)
    median = margins[len(margins) // 2]
    assert f"**median of {median:.1f}%**" in FLAT
    assert f"minimum {min(margins):.1f}%, maximum {max(margins):.1f}%" in FLAT
    assert "the wrong\nnumber to quote on its own" in TEXT
