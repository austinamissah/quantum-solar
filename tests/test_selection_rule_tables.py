"""`docs/results/selection-rule.md`, pinned to its own evaluation.

This write-up needs the gate more than most. Its candidate rules were **fitted** on 40
points, so the only thing separating it from a story is that the criteria and the
held-out set were fixed first and that the discovery cell is excluded. Both of those
are checked here, not assumed.

The document's caveats are pinned alongside its findings, deliberately. A later
edit that keeps "feasible mass picks the argmax in 9 of 9" while dropping "and the two
held-out instances are easy, so P2 does not discriminate" would leave every number
correct and the paper wrong.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from _markdown import flatten, markdown_table as _markdown_table, numbers

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "results" / "selection-rule.md"
PLAN = ROOT / "docs" / "plans" / "selection-rule.md"
DATA = ROOT / "docs" / "results" / "selection_rule.json"

TEXT = DOC.read_text()
FLAT = flatten(TEXT)
STUDY = json.loads(DATA.read_text())
BAR = STUDY["bar"]
CELLS = STUDY["cells"]
HELD_OUT = tuple(STUDY["held_out_instances"])


def sound_cells(instances, *, max_alpha=None, exclude_discovery=True):
    return [
        c for c in CELLS
        if c["instance"] in instances and c["sound"]
        and (max_alpha is None or c["alpha"] <= max_alpha)
        and not (exclude_discovery and c["is_discovery_cell"])
    ]


def test_the_discovery_cell_is_excluded_from_every_verdict():
    """The rules were fitted on instance 1 at α*; that cell cannot be evidence.

    The single most important property of this study. If the discovery cell ever
    leaks into the held-out pool, both verdicts become circular and the write-up
    becomes a description of the data it was fitted to.
    """
    discovery = [c for c in CELLS if c["is_discovery_cell"]]
    assert len(discovery) == 1
    assert (discovery[0]["instance"], discovery[0]["alpha"]) == (
        STUDY["discovery_cell"]["instance"], STUDY["discovery_cell"]["alpha"])
    assert discovery[0]["instance"] not in HELD_OUT
    assert "excluded" in FLAT and "discovery cell" in FLAT


def test_the_confirmation_was_registered_before_the_sweeps_ran():
    named = re.search(r"committed at `([0-9a-f]{7,})`", FLAT).group(1)
    assert STUDY["plan_commit"].startswith(named)
    assert PLAN.exists()


def test_both_verdicts_match_the_evaluation():
    """P1 and P2, at the registered definitions, with their direction checked."""
    v = STUDY["verdicts"]
    _, rows = _markdown_table(TEXT, "| | prediction | measured | outcome |")

    p1 = next(r for r in rows if "P1" in r[0])
    wins, losses, ties = (int(n) for n in numbers(p1[2])[:3])
    assert (wins, losses, ties) == (v["P1_wins"], v["P1_losses"], v["P1_ties"])
    assert v["P1_falsified"] == (wins <= losses)
    assert not v["P1_falsified"] and "**held**" in p1[3]

    p2 = next(r for r in rows if "P2" in r[0])
    found, of = (int(n) for n in numbers(p2[2])[:2])
    assert (found, of) == (v["P2_feasible_mass_found_one"],
                           v["P2_cells_with_a_clearing_tuning"])
    assert v["P2_falsified"] == (found <= of / 2)
    assert not v["P2_falsified"] and "**held**" in p2[3]


def test_P2_does_not_discriminate_and_the_document_says_so():
    """The incumbent scores the same on P2; that caveat must survive editing.

    Reporting 7 of 9 without it would read as evidence for the new rule when it is
    evidence for nothing.
    """
    v = STUDY["verdicts"]
    assert v["P2_lowest_H_found_one"] == v["P2_feasible_mass_found_one"]
    assert f"`<H>` also scored {v['P2_lowest_H_found_one']} of {v['P2_cells_with_a_clearing_tuning']}" in FLAT
    assert "does not discriminate" in FLAT


def operating_band_rows():
    _, rows = _markdown_table(TEXT, "| pool | cells |")
    return rows


@pytest.mark.parametrize("row", operating_band_rows(), ids=["held-out", "instance-1"])
def test_operating_band_row(row):
    """The sound + reproducible band table, recomputed from the evaluation."""
    instances = HELD_OUT if "held-out" in row[0] else (STUDY["discovery_cell"]["instance"],)
    cells = sound_cells(instances, max_alpha=0.03)

    count, feasible_clears, h_clears, argmax = (int(numbers(c)[0]) for c in row[1:5])
    assert count == len(cells)
    assert feasible_clears == sum(1 for c in cells if c["rules"]["feasible_mass"]["picked_clears"])
    assert h_clears == sum(1 for c in cells if c["rules"]["lowest_H"]["picked_clears"])
    assert argmax == sum(
        1 for c in cells
        if abs(c["rules"]["feasible_mass"]["picked_mass"] - c["best_mass"]) < 1e-12)


def test_the_headline_argmax_claim():
    """"selected the single best tuning in the cell, in all nine" -- recomputed."""
    cells = sound_cells((1,) + HELD_OUT, max_alpha=0.03)
    argmax = sum(1 for c in cells
                 if abs(c["rules"]["feasible_mass"]["picked_mass"] - c["best_mass"]) < 1e-12)
    assert argmax == len(cells), "the claim is that it picks the argmax everywhere"
    assert "in all nine" in FLAT and len(cells) == 9


def test_the_hard_instance_is_where_the_rules_differ():
    """instance 1: feasible mass 2 of 2, `<H>` 0 of 2. The comparison that matters."""
    cells = sound_cells((1,), max_alpha=0.03)
    feasible = sum(1 for c in cells if c["rules"]["feasible_mass"]["picked_clears"])
    incumbent = sum(1 for c in cells if c["rules"]["lowest_H"]["picked_clears"])
    assert (feasible, incumbent) == (len(cells), 0)
    assert f"feasible mass clears {feasible} of {len(cells)} and `<H>` clears {incumbent} of {len(cells)}" in FLAT
    assert "weaker evidence by design" in FLAT


def test_the_two_losses_are_in_the_junk_regime():
    """Both P1 losses sit where every rule is ~500x short; the document says so."""
    _, rows = _markdown_table(TEXT, "| cell | feasible mass |")
    losses = [c for c in sound_cells(HELD_OUT)
              if c["rules"]["feasible_mass"]["picked_mass"]
              < c["rules"]["lowest_H"]["picked_mass"]]
    assert len(losses) == len(rows) == STUDY["verdicts"]["P1_losses"]

    for cell, row in zip(sorted(losses, key=lambda c: c["alpha"]), rows):
        assert numbers(row[0])[0] == cell["instance"]
        assert numbers(row[0])[1] == cell["alpha"]
        assert f"{numbers(row[1])[0]:.6f}" == f"{cell['rules']['feasible_mass']['picked_mass']:.6f}"
        assert f"{numbers(row[2])[0]:.6f}" == f"{cell['rules']['lowest_H']['picked_mass']:.6f}"
        assert f"{numbers(row[3])[0]:.4f}" == f"{cell['best_mass']:.4f}"
        # "junk regime" is the claim: both rules are orders short of what was available.
        assert cell["best_mass"] > 50 * max(cell["rules"]["feasible_mass"]["picked_mass"],
                                            cell["rules"]["lowest_H"]["picked_mass"])


def test_the_direct_rule_and_its_shot_cost():
    """The direct rule's 9 of 9 and its mean, against the per-rule table."""
    direct = STUDY["per_rule_held_out"]["best_feasible_mass"]
    shape = STUDY["per_rule_held_out"]["feasible_mass"]
    assert f"**{direct['clearing_cells_found']} of {direct['of']}**" in FLAT
    assert f"**{direct['mean_picked_mass']:.4f}** against {shape['mean_picked_mass']:.4f}" in FLAT
    assert direct["clearing_cells_found"] > shape["clearing_cells_found"]

    # The shot-budget ladder is disclosed in the plan and quoted in the results.
    ladder = re.search(r"\*\*(\d+)%\*\* of the time there, rising to (\d+)% at ([\d,]+), "
                       r"(\d+)% at ([\d,]+)\s*and \*\*(\d+)% at ([\d,]+)\*\*", FLAT)
    assert ladder, "the shot ladder has been reworded"
    assert ladder.group(1) in PLAN.read_text(), "the ladder must match the registration"


def test_the_near_duplicate_caveat_survives():
    """feasible_mass and lowest_participation agree in 14 of 15 cells; say so.

    Two rules agreeing looks like two confirmations. It is one, and the document is
    only accurate while it keeps saying that.
    """
    cells = sound_cells(HELD_OUT, exclude_discovery=True)
    same = sum(1 for c in cells
               if c["rules"]["feasible_mass"]["picked_seed"]
               == c["rules"]["lowest_participation"]["picked_seed"])
    assert f"same tuning in {same} of {len(cells)}" in FLAT
    assert "one result, not two" in FLAT
