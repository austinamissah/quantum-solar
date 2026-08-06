"""IBM Quantum hardware run for the battery-scheduling QAOA circuits.

Three deliberately separated stages:

  (a) optimize  — simulator-only re-optimization of QAOA parameters for the target
                  instances; saves angles to docs/results/hardware_params.json.
                  No network.
  (b) submit    — rebuilds the tuned circuits, transpiles for the selected backend,
                  and runs ONLY SamplerV2 sampling (no optimization on hardware).
                  Dry-run by default; actually spends QPU only with --yes-spend-qpu.
                  Saves counts + actual QPU seconds to docs/results/hardware_counts.json.
  (c) analysis  — compare exact (statevector) vs ideal-simulated vs hardware
                  distributions (see notebooks/experiment_hardware.ipynb). The
                  helpers live here; the notebook renders them.

Targets: primary T=2 and T=3 (seed 0, reps 1 & 2) — where the scaling sweep showed
real probability concentration, so device noise is measurable against a success
signal. A 22-qubit T=6 case is an OPTIONAL, explicitly labeled stretch sample
(--include-stretch): ideal QAOA already fails there, so hardware-vs-ideal
attribution is impossible.

qiskit-ibm-runtime is imported lazily (only in the submit stage), so stages (a)/(c)
and the tests run without it installed.

CLI:
  python scripts/experiment_hardware.py optimize [--include-stretch]
  python scripts/experiment_hardware.py submit [--backend NAME] [--include-stretch] [--yes-spend-qpu]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from qiskit.circuit.library import QAOAAnsatz

from quantum_solar import (
    Encoding,
    PenaltyWeights,
    QAOASolver,
    build_qubo,
    default_weights,
    dp_solve,
    qubo_to_ising,
    synthetic_instance,
)
from quantum_solar.brute_force import enumerate_bitstrings
from quantum_solar.statevector import assert_matches_qiskit, qaoa_probabilities

# Must match the scaling sweep so the instances are identical.
CAPACITY = 3.0
CHARGE_ENERGY = 1.0
INITIAL_SOC = 1.0
QAOA_SEED = 1234
SHOTS = 4096
N_STARTS = 5
MAXITER = 200

PRIMARY_TARGETS = [
    {"T": 2, "seed": 0, "reps": 1},
    {"T": 2, "seed": 0, "reps": 2},
    {"T": 3, "seed": 0, "reps": 1},
    {"T": 3, "seed": 0, "reps": 2},
]
STRETCH_TARGETS = [{"T": 6, "seed": 0, "reps": 1}]

# SoC-bound encodings a target may name. Stored as a string in the params file so
# the record stays JSON and stage (c) can rebuild the exact circuit that ran.
ENCODINGS = {
    "exact": Encoding.EXACT,
    "checkpoint3": Encoding.checkpoint(3),
}

# Pre-registered in docs/plans/hardware-run-encoding.md: does the slack-free
# encoding reduce *device* degradation, or only simulated gate count? Same
# instance, same optimum, same depth -- the encoding is the only variable.
#
#   alpha = 0.021 for BOTH arms. alpha* = span/penalty = 0.0209 is a property of
#     the problem, not the encoding, so one weight serves both.
#   shots are per-target and unequal ON PURPOSE: TVD's shot-noise floor grows
#     with Hilbert-space dimension, so equal shots would hand the 6-qubit circuit
#     an artificial advantage. 4,096 / 65,536 equalises the floor at ~0.042.
#   mitigated targets are the EXPLORATORY arm and gate nothing.
_SF = {"T": 3, "seed": 0, "reps": 1, "alpha": 0.021}
SLACKFREE_TARGETS = [
    {**_SF, "encoding": "exact", "shots": 65536, "mitigated": False},
    {**_SF, "encoding": "checkpoint3", "shots": 4096, "mitigated": False},
    {**_SF, "encoding": "exact", "shots": 65536, "mitigated": True},
    {**_SF, "encoding": "checkpoint3", "shots": 4096, "mitigated": True},
]

# Pre-registered in docs/plans/hardware-run-encoding-replication.md. Three
# circuits in ONE job so they share a calibration snapshot. exact@default is the
# identical circuit July ran, so it is simultaneously the weight contrast and a
# direct drift probe against July's measured k.
# Order is load-bearing: the PRIMARY comparison is the first-listed pair
# (replicate 1), fixed here so it cannot be chosen after seeing which pair is more
# favourable. Replicate 2 is a VARIANCE ESTIMATE and is never pooled into the gap.
REPLICATION_TARGETS = [
    {"T": 3, "seed": 0, "reps": 1, "encoding": "checkpoint3", "alpha": 0.021, "shots": 4096, "replicate": 1},
    {"T": 3, "seed": 0, "reps": 1, "encoding": "exact", "alpha": 0.021, "shots": 65536, "replicate": 1},
    {"T": 3, "seed": 0, "reps": 1, "encoding": "exact", "alpha": 1.0, "shots": 65536},
    {"T": 3, "seed": 0, "reps": 1, "encoding": "checkpoint3", "alpha": 0.021, "shots": 4096, "replicate": 2},
    {"T": 3, "seed": 0, "reps": 1, "encoding": "exact", "alpha": 0.021, "shots": 65536, "replicate": 2},
]

# Pre-registered in docs/plans/hardware-run-spread.md. Two purposes: a
# properly-powered within-job spread estimate on the cp3 arm (10 replicates -- at 5,
# the RESOLVED verdict is unreachable even at zero device variance), and a
# third independent between-run gap measurement. Order is load-bearing -- the
# PRIMARY gap is replicate 1 of each arm, listed first, fixed before submission.
SPREAD_TARGETS = [
    {"T": 3, "seed": 0, "reps": 1, "encoding": "checkpoint3", "alpha": 0.021, "shots": 4096, "replicate": 1},
    {"T": 3, "seed": 0, "reps": 1, "encoding": "exact", "alpha": 0.021, "shots": 65536, "replicate": 1},
] + [
    {"T": 3, "seed": 0, "reps": 1, "encoding": "checkpoint3", "alpha": 0.021, "shots": 4096, "replicate": r}
    for r in (2, 3, 4, 5, 6, 7, 8, 9, 10)
] + [
    {"T": 3, "seed": 0, "reps": 1, "encoding": "exact", "alpha": 0.021, "shots": 65536, "replicate": 2},
]

RESULTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "results"
# hardware_params.json / hardware_counts.json are the provenance record of the
# 2026-07-11 run and are NEVER written by the slackfree plan.
PLANS = {
    "july": {
        "targets": PRIMARY_TARGETS,
        "params": RESULTS_DIR / "hardware_params.json",
        "counts": RESULTS_DIR / "hardware_counts.json",
    },
    "spread": {
        "targets": SPREAD_TARGETS,
        "params": RESULTS_DIR / "hardware_params_spread.json",
        "counts": RESULTS_DIR / "hardware_counts_spread.json",
        "backend": "ibm_fez",
    },
    "replication": {
        "targets": REPLICATION_TARGETS,
        "params": RESULTS_DIR / "hardware_params_replication.json",
        "counts": RESULTS_DIR / "hardware_counts_replication.json",
        "backend": "ibm_fez",
    },
    "slackfree": {
        "targets": SLACKFREE_TARGETS,
        "params": RESULTS_DIR / "hardware_params_slackfree.json",
        "counts": RESULTS_DIR / "hardware_counts_slackfree.json",
        # Pinned in the PLAN, not just at the command line. The quantitative
        # prediction is calibrated on July's ibm_fez circuits and per-device error
        # rates do not transfer across Heron devices, so the baseline holds only
        # if the device is held fixed. Unavailable => fail, never substitute.
        "backend": "ibm_fez",
    },
}
PARAMS_PATH = PLANS["july"]["params"]   # back-compat for stage (c) / the notebook
COUNTS_PATH = PLANS["july"]["counts"]


def target_label(t) -> str:
    """Stable label: encoding, weight, depth, mitigation. Weight is in the label
    because a plan may run the same encoding at two weights as its whole point."""
    enc, alpha = t.get("encoding", "exact"), t.get("alpha", 1.0)
    wtag = "default" if alpha == 1.0 else f"a{alpha:g}"
    tag = "_mit" if t.get("mitigated") else ""
    rep = f"_r{t['replicate']}" if t.get("replicate") else ""
    return f"T{t['T']}_{enc}_{wtag}_reps{t['reps']}{rep}{tag}"


# --- shared circuit/instance construction ------------------------------------

def build_from_record(r):
    """``build_target`` for a target/params record, applying per-record defaults."""
    return build_target(r["T"], r["seed"], r["reps"],
                        encoding=r.get("encoding", "exact"), alpha=r.get("alpha", 1.0))


def build_target(T, seed, reps, encoding="exact", alpha=1.0):
    """Rebuild the instance, QUBO, cost Hamiltonian, and (measurement-free) ansatz.

    ``encoding`` names a key of :data:`ENCODINGS`; ``alpha`` scales all three
    penalties. Both default to what the July run used (exact encoding, unscaled
    ``default_weights``), so existing callers are unaffected.
    """
    problem = synthetic_instance(T, seed=seed, capacity=CAPACITY,
                                 charge_energy=CHARGE_ENERGY, initial_soc=INITIAL_SOC)
    base = default_weights(problem)
    weights = base if alpha == 1.0 else PenaltyWeights(
        alpha * base.mutual_exclusion, alpha * base.soc_bounds, alpha * base.terminal)
    qubo = build_qubo(problem, weights, ENCODINGS[encoding])
    hamiltonian, _ = qubo_to_ising(qubo)
    ansatz = QAOAAnsatz(cost_operator=hamiltonian, reps=reps)
    return problem, qubo, ansatz


def qubo_energy_diagonal(qubo):
    """QUBO energies of every basis state (index i -> bit j = qubit j)."""
    X = enumerate_bitstrings(qubo.num_vars).astype(float)
    return np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset


def basis_masks(problem, qubo):
    """Boolean masks over basis states (index i -> bit j = qubit j): optimal, feasible."""
    energies = qubo_energy_diagonal(qubo)
    opt_mask = np.isclose(energies, energies.min(), atol=1e-6)
    feas_mask = np.array([problem.is_feasible(x)
                          for x in enumerate_bitstrings(qubo.num_vars)])
    return opt_mask, feas_mask


def exact_distribution(qubo, params, reps):
    """Noiseless statevector probabilities of the tuned circuit (indexed by basis int).

    Computed with the NumPy statevector, NOT `Statevector(QAOAAnsatz(...))`: the
    latter matrix-exponentiates the un-decomposed cost layer and dies with
    MemoryError from m=14 up. That ceiling is *below* this script's own stretch
    target — T=6 is m=22 — so the Qiskit path could not evaluate the targets this
    script defines. See quantum_solar.statevector.

    A constant shift of the cost diagonal is a global phase, so the QUBO energies
    serve directly as the cost diagonal in place of the Ising ones.
    """
    return qaoa_probabilities(qubo_energy_diagonal(qubo), params, reps)


# --- stage (c) analysis helpers ----------------------------------------------

def tv_distance(p, q):
    """Total variation distance between two probability vectors."""
    return 0.5 * float(np.abs(np.asarray(p) - np.asarray(q)).sum())


def counts_to_probs(counts, m):
    """Convert a Qiskit counts dict to a probability vector indexed by basis int."""
    probs = np.zeros(2 ** m)
    total = sum(counts.values())
    for key, n in counts.items():
        probs[int(key.replace(" ", ""), 2)] += n / total
    return probs


def scalar_metrics(probs, opt_mask, feas_mask):
    """Optimal-state mass and feasibility rate of a distribution."""
    probs = np.asarray(probs)
    return {
        "optimal_mass": float(probs[opt_mask].sum()),
        "feasibility": float(probs[feas_mask].sum()),
    }


def ideal_sim_for_record(ansatz, record, *, seed=QAOA_SEED):
    """Ideal-sim counts at the record's OWN shot count.

    Use this, not ``ideal_sim_counts``, whenever a plan uses unequal shots. The
    slack-free plan deliberately runs 4,096 / 65,536 to equalise the TVD
    shot-noise floor across dimensions; sampling the reference at the module
    default instead would leave the reference carrying a 4,096-shot floor while
    the hardware side carries a 65,536-shot one, re-inflating exactly the
    asymmetry the unequal shots exist to remove. (Observed: it put the 10-qubit
    circuit's floor at 0.164 instead of 0.043 and inflated its TVD by 35%.)
    """
    return ideal_sim_counts(ansatz, record["params"],
                            shots=int(record.get("shots", SHOTS)), seed=seed)


def ideal_sim_counts(ansatz, params, *, shots=SHOTS, seed=QAOA_SEED):
    """Aer SamplerV2 counts for the tuned circuit (shot noise, no device noise)."""
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_aer import AerSimulator
    from qiskit_aer.primitives import SamplerV2

    qc = ansatz.assign_parameters(list(params))
    qc.measure_all()
    backend = AerSimulator(seed_simulator=seed)
    isa = generate_preset_pass_manager(optimization_level=1, backend=backend).run(qc)
    sampler = SamplerV2(options={"backend_options": {"seed_simulator": seed}})
    return sampler.run([(isa,)], shots=shots).result()[0].data.meas.get_counts()


# --- stage (a): simulator re-optimization ------------------------------------

def validate_statevector(t=2, seed=0, reps_values=(1, 2)):
    """Cross-check the NumPy statevector against Qiskit's, and raise if it drifts.

    Runs at T=2 (m=6), where the Qiskit reference is still cheap; the NumPy path
    is size-independent in its logic, so agreement here validates it at every
    target size. Gates the reported ideal metrics rather than annotating them.
    """
    _, qubo, _ = build_target(t, seed, max(reps_values))
    hamiltonian, _ = qubo_to_ising(qubo)
    rng = np.random.default_rng(0)
    worst = max(assert_matches_qiskit(hamiltonian, rng.uniform(0.0, np.pi, 2 * r), r)
                for r in reps_values)
    print(f"statevector self-check: NumPy vs Qiskit agree to {worst:.1e}", flush=True)


def optimize_params(targets, *, seed=QAOA_SEED, n_starts=N_STARTS, shots=SHOTS,
                    maxiter=MAXITER):
    """Re-optimize QAOA angles on the simulator; return one record per target.

    Reference metrics (ideal_opt_mass, ideal_feasibility) are the EXACT statevector
    values of the tuned circuit — the same 'exact' distribution stage (c) uses.
    """
    validate_statevector()
    records = []
    tuned = {}  # (T, seed, reps, encoding, alpha) -> params; mitigation arms reuse
    for tgt in targets:
        T, s, reps = tgt["T"], tgt["seed"], tgt["reps"]
        encoding, alpha = tgt.get("encoding", "exact"), tgt.get("alpha", 1.0)
        problem, qubo, _ = build_target(T, s, reps, encoding=encoding, alpha=alpha)
        key = (T, s, reps, encoding, alpha)
        if key not in tuned:
            # Mitigation is a sampling-time option, not a circuit change, so a
            # mitigated target reuses its unmitigated twin's angles rather than
            # re-tuning to a different local optimum and confounding the pair.
            result = QAOASolver(reps=reps, n_starts=n_starts, shots=shots, seed=seed,
                                maxiter=maxiter).solve(problem, qubo)
            tuned[key] = [float(x) for x in result.optimal_params]
        params = tuned[key]

        probs = exact_distribution(qubo, params, reps)
        opt_mask, feas_mask = basis_masks(problem, qubo)
        metrics = scalar_metrics(probs, opt_mask, feas_mask)
        records.append({
            "T": T, "seed": s, "reps": reps, "m": qubo.num_vars,
            "encoding": encoding, "alpha": alpha,
            "shots": int(tgt.get("shots", shots)),
            "mitigated": bool(tgt.get("mitigated", False)),
            "replicate": tgt.get("replicate"),
            "params": params,
            "dp_cost": float(dp_solve(problem).true_energy),
            "ideal_opt_mass": metrics["optimal_mass"],
            "ideal_feasibility": metrics["feasibility"],
            "stretch": bool(tgt.get("stretch", False)),
        })
    return records


def run_optimize(include_stretch=False, plan="july", overwrite=False):
    cfg = PLANS[plan]
    params_path = cfg["params"]
    # Refuse to clobber ANY existing params file, not just the July one. Tuned
    # angles are the provenance record of what a run actually executed; if the
    # file is gone, the counts beside it can no longer be reproduced. The guard
    # is on existence, deliberately, so it cannot be defeated by pointing a new
    # plan at the wrong filename.
    if params_path.exists() and not overwrite:
        raise SystemExit(
            f"refusing to overwrite {params_path} — it is the provenance record "
            f"for a run that already happened. Move or delete it deliberately, or "
            f"pass --overwrite if you are certain."
        )
    targets = list(cfg["targets"])
    if include_stretch:
        targets += [dict(t, stretch=True) for t in STRETCH_TARGETS]
    records = optimize_params(targets)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    params_path.write_text(json.dumps(records, indent=2))
    for r in records:
        print(f"{target_label(r):<24} m={r['m']} "
              f"ideal_opt_mass={r['ideal_opt_mass']:.4f} "
              f"ideal_feasibility={r['ideal_feasibility']:.4f}", flush=True)
    print(f"wrote {len(records)} records -> {params_path}", flush=True)


# --- stage (b): submit (sampling only; QPU-gated) ----------------------------

def _coarse_qpu_seconds(n_circuits, shots, depths):
    """Deliberately coarse order-of-magnitude estimate — NOT a quote.

    Actual QPU seconds are recorded post-run from job metadata. ``shots`` may be
    a scalar or a per-circuit sequence; the slack-free plan uses unequal shots by
    design, so a single figure would misestimate it badly.
    """
    if np.isscalar(shots):
        shots = [shots] * n_circuits
    if len(depths) != n_circuits or len(shots) != n_circuits:
        raise ValueError("shots/depths must align with n_circuits")
    return float(sum(2.0 + sh * d * 2e-6 for sh, d in zip(shots, depths)))


def _calibration_snapshot(backend):
    """Median 2-qubit and readout error at submission time.

    Pinning the device removes inter-device variation but NOT temporal drift, and
    the prediction bands were measured on one device on one day. Recording this
    makes drift measurable after the fact instead of merely acknowledged.
    """
    try:
        props = backend.properties()
        if props is None:
            return None
        two_q = [g.parameters[0].value for g in props.gates
                 if len(g.qubits) == 2 and g.parameters
                 and g.parameters[0].name == "gate_error"]
        readout = [props.readout_error(q) for q in range(backend.num_qubits)]
        return {
            "median_2q_gate_error": float(np.median(two_q)) if two_q else None,
            "median_readout_error": float(np.median(readout)) if readout else None,
            "last_update_date": str(getattr(props, "last_update_date", None)),
        }
    except Exception as exc:  # never block a run on a diagnostic
        return {"error": repr(exc)}


def _select_backend(service, min_num_qubits):
    """Least-busy operational Heron device with enough qubits; fall back to any.

    Prefers IBM Heron-family processors; if none is available, falls back to the
    least-busy operational (non-simulator) backend with enough qubits so backend
    selection never hard-fails.
    """
    def is_heron(b):
        try:
            return b.configuration().processor_type.get("family") == "Heron"
        except Exception:
            return False

    try:
        return service.least_busy(operational=True, simulator=False,
                                  min_num_qubits=min_num_qubits, filters=is_heron)
    except Exception:
        return service.least_busy(operational=True, simulator=False,
                                  min_num_qubits=min_num_qubits)


def run_submit(*, backend_name=None, include_stretch=False, yes_spend_qpu=False,
               shots=SHOTS, plan="july"):
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    cfg = PLANS[plan]
    params_path, counts_path = cfg["params"], cfg["counts"]
    if not params_path.exists():
        raise SystemExit(f"{params_path} not found — run `optimize --plan {plan}` first")
    records = json.loads(params_path.read_text())
    if not include_stretch:
        records = [r for r in records if not r.get("stretch")]
    elif not any(r.get("stretch") for r in records):
        print("WARNING: --include-stretch requested but the params file has no "
              "stretch record; run `optimize --include-stretch` first.", flush=True)
    if not records:
        raise SystemExit("no targets to submit (run `optimize` first)")

    # Bare service: saved default account in ~/.qiskit. No legacy channel.
    service = QiskitRuntimeService()
    max_m = max(r["m"] for r in records)
    pinned = cfg.get("backend")
    if backend_name and pinned and backend_name != pinned:
        print(f"WARNING: --backend {backend_name} overrides the plan's pinned "
              f"{pinned}. The prediction is calibrated on {pinned}; per-device "
              f"error rates do not transfer across Heron devices.", flush=True)
    chosen = backend_name or pinned
    if chosen:
        # Deliberately no fallback: a silent substitution would break exactly the
        # calibration assumption the pin exists to protect.
        try:
            backend = service.backend(chosen)
        except Exception as exc:
            raise SystemExit(
                f"pinned backend {chosen!r} is unavailable ({exc}). This plan does "
                f"not substitute another device — its prediction is calibrated on "
                f"{chosen}. Wait for it, or amend the plan deliberately."
            ) from exc
        if not backend.status().operational:
            raise SystemExit(f"pinned backend {chosen!r} is not operational; not substituting.")
    else:
        backend = _select_backend(service, max_m)
    # optimization_level=3, not 1: on identical circuits this cuts transpiled
    # 2-qubit gates 12-18% (July's four circuits: 37/77/124/290 -> 33/71/109/237)
    # at no cost. Device-noise TVD tracks 2-qubit gate count monotonically (July:
    # 0.119/0.203/0.383/0.459), so fewer gates is strictly better here.
    pass_manager = generate_preset_pass_manager(optimization_level=3, backend=backend,
                                                seed_transpiler=QAOA_SEED)

    # Transpile once per distinct CIRCUIT and reuse. Mitigation is a sampler
    # option, not a circuit change, so a mitigated target must run the identical
    # transpiled circuit as its unmitigated twin -- otherwise routing
    # stochasticity is folded into the mitigation comparison. (Observed: the same
    # circuit transpiled to 113 and 98 two-qubit gates on consecutive calls.)
    transpiled = {}
    circuits, labels, shot_counts = [], [], []
    for r in records:
        key = (r["T"], r["seed"], r["reps"], r.get("encoding", "exact"), r.get("alpha", 1.0))
        if key not in transpiled:
            _, _, ansatz = build_from_record(r)
            qc = ansatz.assign_parameters(r["params"])
            qc.measure_all()
            transpiled[key] = pass_manager.run(qc)
        circuits.append(transpiled[key])
        labels.append(target_label(r))
        shot_counts.append(int(r.get("shots", shots)))

    depths = [c.depth() for c in circuits]
    two_qubit_gates = [c.num_nonlocal_gates() for c in circuits]
    # Mitigation is a Sampler-level option, not per-PUB, so each setting is its
    # own job. The exploratory arm therefore never shares a job with the primary.
    groups = sorted({bool(r.get("mitigated", False)) for r in records})

    print("=== pre-submission summary ===")
    print(f"plan            : {plan}")
    print(f"backend         : {backend.name}"
          + ("  (PINNED by plan)" if cfg.get("backend") == backend.name else ""))
    print(f"jobs            : {len(groups)}"
          + ("  (unmitigated / mitigated)" if len(groups) > 1 else ""))
    print(f"circuits        : {len(circuits)}")
    print(f"{'label':<24} {'m':>3} {'shots':>7} {'2Q':>5} {'depth':>6} {'mitigated':>10}")
    for r, lab, sh, g2, d in zip(records, labels, shot_counts, two_qubit_gates, depths):
        print(f"{lab:<24} {r['m']:>3} {sh:>7} {g2:>5} {d:>6} "
              f"{str(bool(r.get('mitigated', False))):>10}")
    print(f"est. QPU seconds: ~{_coarse_qpu_seconds(len(circuits), shot_counts, depths):.1f}"
          f"  (COARSE)")

    if not yes_spend_qpu:
        print("DRY RUN — no QPU spent. Pass --yes-spend-qpu to submit.", flush=True)
        return
    # Same guard as the params file: counts are the provenance record of a run
    # that spent QPU and cannot be regenerated. Refuse rather than clobber.
    if counts_path.exists():
        raise SystemExit(
            f"refusing to overwrite {counts_path} — it is the record of a run that "
            f"already spent QPU and cannot be reproduced. Move or delete it deliberately."
        )

    results, job_ids, actual = [None] * len(records), [], 0.0
    for mitigated in groups:
        idx = [i for i, r in enumerate(records) if bool(r.get("mitigated", False)) is mitigated]
        sampler = SamplerV2(mode=backend)
        if mitigated:
            sampler.options.dynamical_decoupling.enable = True
            sampler.options.dynamical_decoupling.sequence_type = "XY4"
            sampler.options.twirling.enable_measure = True
        job = sampler.run([(circuits[i], None, shot_counts[i]) for i in idx])
        print(f"submitted job {job.job_id()} (mitigated={mitigated}) to {backend.name}; "
              f"waiting...", flush=True)
        res = job.result()
        job_ids.append(job.job_id())
        for slot, i in enumerate(idx):
            results[i] = res[slot].data.meas.get_counts()
        try:
            actual += float(job.usage())
        except Exception:
            actual = None if actual is None else actual

    out = {
        "plan": plan,
        "backend": backend.name,
        "backend_calibration": _calibration_snapshot(backend),
        "job_ids": job_ids,
        "actual_qpu_seconds": actual,
        "results": [
            {**{k: records[i][k] for k in ("T", "seed", "reps", "m") if k in records[i]},
             "label": labels[i],
             "encoding": records[i].get("encoding", "exact"),
             "alpha": records[i].get("alpha", 1.0),
             "mitigated": bool(records[i].get("mitigated", False)),
             "shots": shot_counts[i],
             "two_qubit_gates": two_qubit_gates[i],
             "depth": depths[i],
             "counts": results[i]}
            for i in range(len(records))
        ],
    }
    counts_path.write_text(json.dumps(out, indent=2))
    print(f"actual QPU seconds: {actual}; wrote -> {counts_path}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="stage", required=True)

    p_opt = sub.add_parser("optimize", help="stage (a): simulator re-optimization")
    p_opt.add_argument("--include-stretch", action="store_true")
    p_opt.add_argument("--plan", default="july", choices=sorted(PLANS))
    p_opt.add_argument("--overwrite", action="store_true",
                       help="allow clobbering an existing params file (provenance record)")

    p_sub = sub.add_parser("submit", help="stage (b): sample on hardware (QPU-gated)")
    p_sub.add_argument("--backend", default=None)
    p_sub.add_argument("--include-stretch", action="store_true")
    p_sub.add_argument("--yes-spend-qpu", action="store_true")
    p_sub.add_argument("--plan", default="july", choices=sorted(PLANS))

    args = parser.parse_args()
    if args.stage == "optimize":
        run_optimize(include_stretch=args.include_stretch, plan=args.plan,
                     overwrite=args.overwrite)
    elif args.stage == "submit":
        run_submit(backend_name=args.backend, include_stretch=args.include_stretch,
                   yes_spend_qpu=args.yes_spend_qpu, plan=args.plan)


if __name__ == "__main__":
    main()
