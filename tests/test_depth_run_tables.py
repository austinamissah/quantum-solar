"""The tables in ``hardware-run-depth.md``, pinned to the run's own artifacts.

This one differs from ``test_hardware_run_tables.py``: those write-ups report runs
whose raw counts predate the committed artifacts, so they can only be held to their
internal arithmetic. Here the counts *are* committed
(``hardware_counts_depth.json``) alongside the angles that produced them
(``hardware_params_depth.json``), so every published figure is recomputed from the
counts rather than checked for self-consistency.

That matters most for the verdict. The document says a registered prediction was
falsified, which is a claim about a number crossing a threshold fixed in advance;
both the number and the threshold are checked here against the artifact and the
plan respectively, so neither can drift free of the other.

The bootstrap CIs are **not** pinned. They are a seeded resample and reproducing
them would pin the seed rather than the result; what is pinned is that the
intervals published exclude zero, which is the only property the write-up leans on.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import experiment_hardware as hw  # noqa: E402

from _markdown import flatten, markdown_table as _markdown_table, numbers  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "results" / "hardware-run-depth.md"
PLAN = ROOT / "docs" / "plans" / "hardware-run-depth.md"
COUNTS = ROOT / "docs" / "results" / "hardware_counts_depth.json"
PARAMS = ROOT / "docs" / "results" / "hardware_params_depth.json"

TEXT = DOC.read_text()
FLAT = flatten(TEXT)
PLAN_FLAT = flatten(PLAN.read_text())


def measured() -> dict[tuple[int, int], dict]:
    """(reps, replicate) -> every quantity the write-up prints, from the counts."""
    blob = json.loads(COUNTS.read_text())
    params = {hw.target_label(r): r for r in json.loads(PARAMS.read_text())}
    out = {}
    for row in blob["results"]:
        rec = params[row["label"]]
        problem, qubo, _ = hw.build_target(
            rec["T"], rec["seed"], rec["reps"],
            encoding=rec["encoding"], alpha=rec["alpha"],
        )
        opt_mask, feas_mask = hw.basis_masks(problem, qubo)
        n = 2 ** row["m"]
        probs = hw.counts_to_probs(row["counts"], row["m"])
        ideal = hw.exact_distribution(qubo, rec["params"], rec["reps"])
        uniform = np.full(n, 1.0 / n)
        m_hw = hw.scalar_metrics(probs, opt_mask, feas_mask)
        m_id = hw.scalar_metrics(ideal, opt_mask, feas_mask)
        tvd = hw.tv_distance(probs, ideal)
        tv_unif = hw.tv_distance(uniform, ideal)
        out[(rec["reps"], rec["replicate"])] = {
            "gates": row["two_qubit_gates"],
            "opt": m_hw["optimal_mass"], "feas": m_hw["feasibility"],
            "ideal_opt": m_id["optimal_mass"], "ideal_feas": m_id["feasibility"],
            "tvd": tvd, "tv_unif": tv_unif, "normalized": tvd / tv_unif,
        }
    return out


M = measured()


def test_the_run_is_the_one_the_document_names():
    blob = json.loads(COUNTS.read_text())
    assert blob["backend"] == "ibm_fez"
    assert blob["job_ids"] == ["da75ik6sidac73aetu50"]
    assert f"{blob['actual_qpu_seconds']:.1f}" == "6.0"
    assert "da75ik6sidac73aetu50" in FLAT
    assert "**6.0 QPU seconds**" in FLAT


CIRCUIT_ROWS = [
    ("reps=1 r1", 1, 1), ("reps=2 r1", 2, 1),
    ("reps=1 r2", 1, 2), ("reps=2 r2", 2, 2),
]


@pytest.mark.parametrize("label,reps,rep", CIRCUIT_ROWS, ids=[c[0] for c in CIRCUIT_ROWS])
def test_each_circuit_row_is_recomputed_from_the_counts(label, reps, rep):
    _, rows = _markdown_table(TEXT, "| circuit | 2Q |")
    row = next(r for r in rows if label.replace("=", "=") in r[0])
    gates, opt, feas, tvd, tv_unif, norm = (float(numbers(c)[0]) for c in row[1:7])
    got = M[(reps, rep)]
    assert int(gates) == got["gates"]
    assert f"{got['opt']:.5f}" == f"{opt:.5f}"
    assert f"{got['feas']:.5f}" == f"{feas:.5f}"
    assert f"{got['tvd']:.4f}" == f"{tvd:.4f}"
    assert f"{got['tv_unif']:.4f}" == f"{tv_unif:.4f}"
    assert f"{got['normalized']:.4f}" == f"{norm:.4f}"


@pytest.mark.parametrize("rep,key,stated", [
    (1, "opt", 0.03613), (1, "feas", 0.07959),
    (2, "opt", 0.03320), (2, "feas", 0.08276),
])
def test_the_published_differences_are_the_subtraction(rep, key, stated):
    got = M[(2, rep)][key] - M[(1, rep)][key]
    assert f"{got:.5f}" == f"{stated:.5f}"


@pytest.mark.parametrize("rep,reps,stated", [
    (1, 1, 0.850), (1, 2, 0.845), (2, 1, 0.750), (2, 2, 0.760),
])
def test_retention_is_the_quotient_it_claims_to_be(rep, reps, stated):
    """Retention = hardware optimal mass / ideal optimal mass, nothing else."""
    got = M[(reps, rep)]["opt"] / M[(reps, rep)]["ideal_opt"]
    assert f"{got:.3f}" == f"{stated:.3f}"


def test_this_job_did_show_equal_retention_and_the_document_says_it_did_not_replicate():
    """This job's data really did show equal retention. It did not replicate.

    Kept, because the claim was published and the correction is only checkable if
    the thing corrected is still verifiable: the numbers below are what this job
    measured, and the write-up now carries a correction saying a second job 36
    minutes later did not reproduce them
    (``tests/test_depth_replication_tables.py`` pins that side).

    So this asserts a historical fact about one job, not a standing claim about
    these circuits.
    """
    for rep in (1, 2):
        r1 = M[(1, rep)]["opt"] / M[(1, rep)]["ideal_opt"]
        r2 = M[(2, rep)]["opt"] / M[(2, rep)]["ideal_opt"]
        assert abs(r1 - r2) < 0.02, f"replicate {rep}: retention {r1:.3f} vs {r2:.3f}"
    assert "**Correction, 2026-08-26.**" in FLAT
    assert "Equal retention was a property of that job" in FLAT


def test_the_verdict_crosses_the_threshold_the_plan_registered():
    """The falsification claim, against the plan's own number rather than a repeat.

    The threshold is read out of the pre-registration, so editing one side without
    the other fails here.
    """
    threshold = float(
        __import__("re").search(
            r"Threshold: a difference in hardware optimal mass of ([\d.]+)", PLAN_FLAT
        ).group(1)
    )
    assert f"{threshold:.5f}" == "0.00765"
    measured_diff = M[(2, 1)]["opt"] - M[(1, 1)]["opt"]
    assert measured_diff > threshold
    assert f"{measured_diff / threshold:.1f}" == "4.7"
    assert "**4.7x**" in FLAT
    assert "FALSIFIED" in FLAT


def test_the_secondary_moved_opposite_to_its_prediction():
    """Predicted negative, measured positive — the write-up's stronger claim."""
    assert "−0.018976" in FLAT
    assert M[(2, 1)]["feas"] - M[(1, 1)]["feas"] > 0


def test_the_replicate_spread_is_reported_and_is_the_stated_fraction():
    """The caveat that most nearly threatens the verdict is pinned too."""
    spread = abs(M[(1, 1)]["opt"] - M[(1, 2)]["opt"])
    assert f"{spread:.5f}" == "0.00464"
    assert f"{100 * spread / 0.00765:.0f}" == "61"
    assert "61% of the registered threshold" in FLAT
