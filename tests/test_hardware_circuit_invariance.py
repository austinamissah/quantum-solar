"""Every committed hardware circuit must still rebuild to its recorded metrics.

The params files under ``docs/results/`` are the provenance record of what ran on
``ibm_fez``: the tuned angles, and the ideal metrics those angles imply. The counts
beside them are only interpretable against those metrics, so if the code that
rebuilds a circuit drifts, every published hardware number silently loses its
baseline — and nothing else in the suite would notice, because the recorded JSON
does not change.

That is not a hypothetical risk here. ``build_target`` passes **none** of
``sell_price`` / ``export_ratio`` / ``charge_efficiency`` / ``discharge_efficiency``
/ ``discharge_energy``, all of which became live parameters after the hardware runs
were recorded. The circuits are therefore conducted in an implicit regime — net
metered, lossless, symmetric rates — that holds only while those defaults hold. So
this module asserts two things:

1. the **regime**, explicitly, with the reason each part of it matters, and
2. the **metrics**, rebuilt from the committed angles under current code.

Run it before any future submission. See ``docs/LESSONS.md`` §7 on derived
artifacts being claims that go stale silently.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import experiment_hardware as hw  # noqa: E402

RESULTS = Path(__file__).resolve().parents[1] / "docs" / "results"
PARAMS_FILES = [
    "hardware_params.json",
    "hardware_params_depth.json",
    "hardware_params_replication.json",
    "hardware_params_slackfree.json",
    "hardware_params_spread.json",
]

# Residuals are float-reassociation only. The feasibility mask dominates: it is a
# Python loop over `is_feasible`, so it accumulates slightly more than the
# vectorized mass. 1e-12 is far above what reassociation produces (~5e-15 measured)
# and far below any change that would matter to a published number.
ATOL = 1e-12


def records(filename):
    path = RESULTS / filename
    if not path.exists():
        pytest.skip(f"{filename} not committed")
    return json.loads(path.read_text())


def rebuild(record):
    """Recompute (m, ideal optimal mass, ideal feasibility) from committed angles."""
    problem, qubo, _ = hw.build_target(
        record["T"], record["seed"], record["reps"],
        encoding=record.get("encoding", "exact"), alpha=record.get("alpha", 1.0),
    )
    probs = hw.exact_distribution(qubo, record["params"], record["reps"])
    opt_mask, feas_mask = hw.basis_masks(problem, qubo)
    metrics = hw.scalar_metrics(probs, opt_mask, feas_mask)
    return qubo.num_vars, metrics["optimal_mass"], metrics["feasibility"], problem


@pytest.mark.parametrize("filename", PARAMS_FILES)
def test_recorded_circuits_rebuild_to_their_metrics(filename):
    """The committed angles must still imply the committed ideal metrics."""
    rows = records(filename)
    assert rows, f"{filename} is empty"
    for record in rows:
        m, mass, feasibility, _ = rebuild(record)
        label = f"{filename}:{hw.target_label(record)}"
        assert m == record["m"], f"{label}: qubit count moved {record['m']} -> {m}"
        assert mass == pytest.approx(record["ideal_opt_mass"], abs=ATOL), label
        assert feasibility == pytest.approx(record["ideal_feasibility"], abs=ATOL), label


@pytest.mark.parametrize("filename", PARAMS_FILES)
def test_recorded_circuits_are_built_in_the_pinned_regime(filename):
    """The circuits assume net metering, no losses, and symmetric rates.

    Each of these silently changes the *circuit*, not just the cost, so a changed
    default would invalidate the recorded gate counts and metrics rather than
    merely shifting a dollar figure:

    * a ``sell_price`` below ``price`` makes the bill piecewise, which adds
      ``c_j*d_j`` terms to the QUBO and moves the 46/106 two-qubit gate counts;
    * asymmetric charge/discharge energy refines the SoC grid to their GCD, which
      widens the exact encoding's slack register and changes ``m``;
    * efficiencies below 1 rescale the objective relative to the penalties.
    """
    for record in records(filename):
        _, _, _, problem = rebuild(record)
        label = f"{filename}:{hw.target_label(record)}"
        assert problem.is_net_metered, f"{label}: export price no longer equals import"
        assert problem.sell_price is None, f"{label}: sell_price is now set"
        assert problem.charge_efficiency == 1.0, f"{label}: charging is now lossy"
        assert problem.discharge_efficiency == 1.0, f"{label}: discharging is now lossy"
        assert problem.charge_energy == problem.discharge_energy, (
            f"{label}: rates are now asymmetric, so the SoC grid has refined"
        )


def test_every_committed_params_file_is_covered():
    """A new params file must be added to PARAMS_FILES, not silently skipped."""
    on_disk = {p.name for p in RESULTS.glob("hardware_params*.json")}
    assert on_disk == set(PARAMS_FILES), (
        f"params files on disk {sorted(on_disk)} do not match the checked list "
        f"{sorted(PARAMS_FILES)}; add new ones so they are covered too"
    )


def test_the_check_would_actually_catch_drift():
    """Guard the guard: perturbing an angle must break the metric assertion.

    Without this, a rebuild that silently returned the recorded values (or a
    tolerance wide enough to swallow anything) would pass and prove nothing.
    """
    record = dict(records("hardware_params.json")[0])
    record["params"] = [p + 0.05 for p in record["params"]]
    _, mass, _, _ = rebuild(record)
    assert abs(mass - record["ideal_opt_mass"]) > ATOL
