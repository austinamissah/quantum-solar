"""The tables in ``hardware-run-depth-replication.md``, and the cross-run claims.

Two runs measured the same quantity with the same committed angles, so this module
holds a property the single-run tests cannot: **the four published differences are
recomputed from two different counts files**, and the claim that the effect
replicated is a statement about both together.

It also pins the harder half. The replication *withdrew* the first run's stated
mechanism, and a withdrawal is only meaningful if the numbers behind it are
checkable: the retention gaps on both sides are recomputed here, so neither "it
agreed then" nor "it did not agree now" can drift into prose.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import experiment_hardware as hw  # noqa: E402

from _markdown import flatten, markdown_table as _markdown_table, numbers  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "results"
DOC = RESULTS / "hardware-run-depth-replication.md"
PLAN = ROOT / "docs" / "plans" / "hardware-run-depth-replication.md"
PARAMS = RESULTS / "hardware_params_depth.json"

TEXT = DOC.read_text()
FLAT = flatten(TEXT)
PLAN_FLAT = flatten(PLAN.read_text())

THRESHOLD = 0.00765


def measured(counts_name: str) -> dict[tuple[int, int], dict]:
    blob = json.loads((RESULTS / counts_name).read_text())
    params = {hw.target_label(r): r for r in json.loads(PARAMS.read_text())}
    out = {}
    for row in blob["results"]:
        rec = params[row["label"]]
        problem, qubo, _ = hw.build_target(
            rec["T"], rec["seed"], rec["reps"],
            encoding=rec["encoding"], alpha=rec["alpha"],
        )
        opt_mask, feas_mask = hw.basis_masks(problem, qubo)
        probs = hw.counts_to_probs(row["counts"], row["m"])
        ideal = hw.exact_distribution(qubo, rec["params"], rec["reps"])
        uniform = np.full(2 ** row["m"], 1.0 / 2 ** row["m"])
        m_hw = hw.scalar_metrics(probs, opt_mask, feas_mask)
        m_id = hw.scalar_metrics(ideal, opt_mask, feas_mask)
        tvd = hw.tv_distance(probs, ideal)
        tv_unif = hw.tv_distance(uniform, ideal)
        out[(rec["reps"], rec["replicate"])] = {
            "gates": row["two_qubit_gates"], "opt": m_hw["optimal_mass"],
            "feas": m_hw["feasibility"], "tvd": tvd, "tv_unif": tv_unif,
            "normalized": tvd / tv_unif,
            "retention": m_hw["optimal_mass"] / m_id["optimal_mass"],
        }
    return out


RUN1 = measured("hardware_counts_depth.json")
RUN2 = measured("hardware_counts_depth_replication.json")


def test_the_two_runs_flew_identical_circuits():
    """The design claim the whole comparison rests on.

    If the angles differed, the calibration window would not be the only variable
    and the run would answer a different question than the one registered.
    """
    a = json.loads((RESULTS / "hardware_counts_depth.json").read_text())
    b = json.loads((RESULTS / "hardware_counts_depth_replication.json").read_text())
    assert a["job_ids"] != b["job_ids"], "the same job cannot replicate itself"
    for x, y in zip(a["results"], b["results"]):
        assert x["label"] == y["label"]
        assert x["two_qubit_gates"] == y["two_qubit_gates"]
        assert x["shots"] == y["shots"]
    assert "identical to the first run's" in FLAT
    assert b["job_ids"] == ["da765hk6l22c73dn5et0"]
    assert f"{b['actual_qpu_seconds']:.1f}" == "6.0"


CIRCUIT_ROWS = [
    ("reps=1 r1", 1, 1), ("reps=2 r1", 2, 1),
    ("reps=1 r2", 1, 2), ("reps=2 r2", 2, 2),
]


@pytest.mark.parametrize("label,reps,rep", CIRCUIT_ROWS, ids=[c[0] for c in CIRCUIT_ROWS])
def test_each_circuit_row_is_recomputed_from_this_run_s_counts(label, reps, rep):
    _, rows = _markdown_table(TEXT, "| circuit | 2Q |")
    row = next(r for r in rows if label in r[0])
    gates, opt, feas, tvd, tv_unif, norm = (float(numbers(c)[0]) for c in row[1:7])
    got = RUN2[(reps, rep)]
    assert int(gates) == got["gates"]
    assert f"{got['opt']:.5f}" == f"{opt:.5f}"
    assert f"{got['feas']:.5f}" == f"{feas:.5f}"
    assert f"{got['tvd']:.4f}" == f"{tvd:.4f}"
    assert f"{got['normalized']:.4f}" == f"{norm:.4f}"


@pytest.mark.parametrize("run,rep,stated", [
    ("run1", 1, 0.03613), ("run1", 2, 0.03320),
    ("run2", 1, 0.03027), ("run2", 2, 0.03394),
])
def test_the_cross_run_table_is_recomputed_from_both_counts_files(run, rep, stated):
    src = RUN1 if run == "run1" else RUN2
    got = src[(2, rep)]["opt"] - src[(1, rep)]["opt"]
    assert f"{got:.5f}" == f"{stated:.5f}"


def test_all_four_differences_clear_the_registered_threshold():
    """The REPLICATED verdict, against the threshold rather than a restatement."""
    for src, name in ((RUN1, "run 1"), (RUN2, "run 2")):
        for rep in (1, 2):
            d = src[(2, rep)]["opt"] - src[(1, rep)]["opt"]
            assert d > THRESHOLD, f"{name} replicate {rep}: {d:.5f}"
    assert "REPLICATED" in FLAT
    spread = abs((RUN2[(2, 1)]["opt"] - RUN2[(1, 1)]["opt"])
                 - (RUN1[(2, 1)]["opt"] - RUN1[(1, 1)]["opt"]))
    assert f"{spread:.5f}" == "0.00586"
    assert spread < THRESHOLD


RETENTION_ROWS = [
    ("run 1 r1", RUN1, 1, 0.850, 0.845, 0.005),
    ("run 1 r2", RUN1, 2, 0.750, 0.760, 0.011),
    ("run 2 r1", RUN2, 1, 0.834, 0.771, 0.063),
    ("run 2 r2", RUN2, 2, 0.824, 0.807, 0.017),
]


@pytest.mark.parametrize(
    "label,src,rep,shallow,deep,gap", RETENTION_ROWS,
    ids=[r[0].replace(" ", "_") for r in RETENTION_ROWS],
)
def test_the_retention_table_is_recomputed_on_both_sides(label, src, rep, shallow, deep, gap):
    """Both halves of the withdrawal: what agreed, and what then did not."""
    a, b = src[(1, rep)]["retention"], src[(2, rep)]["retention"]
    assert f"{a:.3f}" == f"{shallow:.3f}"
    assert f"{b:.3f}" == f"{deep:.3f}"
    assert f"{abs(a - b):.3f}" == f"{gap:.3f}"


def test_the_mechanism_prediction_is_falsified_by_its_own_stated_bound():
    """The plan predicted agreement within 0.02 in EACH replicate. One failed."""
    bound = float(re.search(r"retention\s+again agree within ([\d.]+)", PLAN_FLAT).group(1))
    assert f"{bound:.2f}" == "0.02"
    gaps = [abs(RUN2[(1, rep)]["retention"] - RUN2[(2, rep)]["retention"]) for rep in (1, 2)]
    assert any(g > bound for g in gaps), "nothing failed; the write-up says one did"
    assert not all(g > bound for g in gaps), "both failed; the write-up says one passed"
    assert "does NOT" in FLAT or "did not replicate" in FLAT


def test_normalized_tvd_was_flat_in_run_one_and_is_not_in_run_two():
    """The plainest form of the withdrawal, recomputed rather than quoted."""
    flat = abs(RUN1[(1, 1)]["normalized"] - RUN1[(2, 1)]["normalized"])
    not_flat = abs(RUN2[(1, 1)]["normalized"] - RUN2[(2, 1)]["normalized"])
    assert flat < 0.02, f"run 1 was not flat after all: {flat:.4f}"
    assert not_flat > 0.15, f"run 2 looks flat too: {not_flat:.4f}"
    assert RUN2[(2, 1)]["normalized"] > RUN2[(1, 1)]["normalized"]


def test_the_surviving_explanation_is_arithmetic_that_holds():
    """'It degrades more but still finishes ahead' — checked, not asserted."""
    deep, shallow = RUN2[(2, 1)], RUN2[(1, 1)]
    assert deep["retention"] < shallow["retention"], "the deeper arm did not degrade more"
    assert deep["opt"] > shallow["opt"], "the deeper arm did not finish ahead"
    assert "large enough for it to finish ahead even when it degrades more" in FLAT


def test_the_noise_model_still_overpredicts_both_arms():
    """The LESSONS claim this run could have overturned, and did not."""
    for gates, key in ((46, (1, 1)), (112, (2, 1))):
        eps = 1 - (1 - 0.0132) ** gates
        assert RUN2[key]["normalized"] < eps, f"{gates} gates: model no longer overpredicts"
    assert "still overpredicting" in FLAT
