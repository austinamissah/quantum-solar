"""The table in ``selection-rule-hardware-tuning.md``, pinned to its artifact.

Unlike the hardware write-ups, nothing here is a record of something unrepeatable:
every figure is a function of the restart pool stored in
``docs/results/hardware_params_depth.json``, so each one is recomputed from that
file rather than merely checked for internal arithmetic.

What that buys: if the selection rule, the metric, or the recorded pool ever
changes, this fails rather than the document quietly becoming false. The write-up
is an *unregistered* observation, which makes pinning it more important, not less —
it has no pre-registration to be checked against.

Deliberately not covered: the 5-vs-40 corollary. The 5-start params file was
overwritten, so there is no committed artifact for it; the document says so and
gives the two commands that reproduce it. A test that re-ran them would take
minutes and would be pinning a fresh computation rather than the record.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from _markdown import flatten, markdown_table as _markdown_table, numbers

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "results" / "selection-rule-hardware-tuning.md"
ARTIFACT = ROOT / "docs" / "results" / "hardware_params_depth.json"

TEXT = DOC.read_text()
FLAT = flatten(TEXT)


def markdown_table(header_contains: str):
    return _markdown_table(TEXT, header_contains)


def pools() -> dict[int, list[dict]]:
    """The recorded restart pool per depth, from the params artifact."""
    records = json.loads(ARTIFACT.read_text())
    out = {}
    for r in records:
        if r.get("candidates"):
            out[r["reps"]] = r["candidates"]
    return out


POOLS = pools()


def picks(pool):
    """(lowest-H pick, feasible-mass pick) — the two rules on one pool."""
    H = np.array([c["H"] for c in pool])
    mass = np.array([c["feasible_mass"] for c in pool])
    return pool[int(np.argmin(H))], pool[int(np.argmax(mass))]


def test_the_artifact_records_a_pool_for_both_depths():
    """Without both pools the document's central comparison is unbacked."""
    assert set(POOLS) == {1, 2}, f"expected pools for reps 1 and 2, got {sorted(POOLS)}"
    for reps, pool in POOLS.items():
        assert len(pool) == 40, f"reps={reps} pool is {len(pool)}, not the documented 40"


def doc_rows() -> list[tuple[int, str, float, float, float, int, int]]:
    _, rows = markdown_table("| arm | rule |")
    parsed = []
    for row in rows:
        reps = int(numbers(row[0])[0])
        rule = row[1].strip("*")
        h, opt, mass = (float(numbers(c)[0]) for c in row[2:5])
        rank, total = (int(n) for n in numbers(row[5])[:2])
        parsed.append((reps, rule, h, opt, mass, rank, total))
    return parsed


DOC_ROWS = doc_rows()


@pytest.mark.parametrize(
    "reps,rule,h,opt,mass,rank,total",
    DOC_ROWS,
    ids=[f"reps{r}-{rule.replace(' ', '_')}" for r, rule, *_ in DOC_ROWS],
)
def test_each_row_is_the_rule_applied_to_the_recorded_pool(
    reps, rule, h, opt, mass, rank, total
):
    """Every printed row is what that rule selects from the stored 40 restarts."""
    pool = POOLS[reps]
    by_h, by_mass = picks(pool)
    chosen = by_h if rule == "lowest ⟨H⟩" else by_mass

    assert f"{chosen['H']:.6f}" == f"{h:.6f}"
    assert f"{chosen['optimal_mass']:.6f}" == f"{opt:.6f}"
    assert f"{chosen['feasible_mass']:.6f}" == f"{mass:.6f}"

    masses = np.array([c["feasible_mass"] for c in pool])
    assert total == len(pool)
    assert rank == int((masses > chosen["feasible_mass"]).sum()) + 1


@pytest.mark.parametrize("reps,field,key,stated", [
    (1, "feasible mass", "feasible_mass", 3.18),
    (1, "optimal mass", "optimal_mass", 3.11),
    (2, "feasible mass", "feasible_mass", 5.65),
    (2, "optimal mass", "optimal_mass", 6.54),
])
def test_the_stated_margins_are_the_two_picks_divided(reps, field, key, stated):
    """The percentage gains are quotients of the table, not free-standing claims."""
    by_h, by_mass = picks(POOLS[reps])
    got = 100.0 * (by_mass[key] / by_h[key] - 1.0)
    assert f"{got:.2f}" == f"{stated:.2f}", f"reps={reps} {field}: {got:.2f}% vs {stated}%"


@pytest.mark.parametrize("reps,stated", [(1, -0.9681), (2, -0.9554)])
def test_the_correlations_are_recomputed_from_the_pool(reps, stated):
    pool = POOLS[reps]
    H = np.array([c["H"] for c in pool])
    mass = np.array([c["feasible_mass"] for c in pool])
    assert f"{np.corrcoef(H, mass)[0, 1]:.4f}" == f"{stated:.4f}"


def test_the_rule_takes_a_worse_H_in_both_arms():
    """The document's stated mechanism, asserted rather than described.

    If the mass-best restart were also the ⟨H⟩-best, the write-up would have no
    finding — the two rules would agree and there would be nothing to replicate.
    """
    assert "takes a **worse ⟨H⟩**" in FLAT
    for reps in (1, 2):
        by_h, by_mass = picks(POOLS[reps])
        assert by_mass["H"] > by_h["H"], f"reps={reps}: the rules picked the same point"
        assert by_mass["feasible_mass"] > by_h["feasible_mass"]


def test_it_says_plainly_that_it_was_not_pre_registered():
    """The one claim that cannot be recomputed, and the one most worth keeping.

    Every other document under docs/results/ names the commit that registered it.
    This one has none, and a reader who assumes the usual discipline would
    over-read it.
    """
    assert "**This was not pre-registered.**" in FLAT
    assert "weaker evidence than a registered one" in FLAT
