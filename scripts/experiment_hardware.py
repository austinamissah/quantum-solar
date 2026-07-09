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
from qiskit.quantum_info import Statevector

from quantum_solar import (
    QAOASolver,
    build_qubo,
    default_weights,
    dp_solve,
    qubo_to_ising,
    synthetic_instance,
)
from quantum_solar.brute_force import enumerate_bitstrings

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

RESULTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "results"
PARAMS_PATH = RESULTS_DIR / "hardware_params.json"
COUNTS_PATH = RESULTS_DIR / "hardware_counts.json"


# --- shared circuit/instance construction ------------------------------------

def build_target(T, seed, reps):
    """Rebuild the instance, QUBO, cost Hamiltonian, and (measurement-free) ansatz."""
    problem = synthetic_instance(T, seed=seed, capacity=CAPACITY,
                                 charge_energy=CHARGE_ENERGY, initial_soc=INITIAL_SOC)
    qubo = build_qubo(problem, default_weights(problem))
    hamiltonian, _ = qubo_to_ising(qubo)
    ansatz = QAOAAnsatz(cost_operator=hamiltonian, reps=reps)
    return problem, qubo, ansatz


def basis_masks(problem, qubo):
    """Boolean masks over basis states (index i -> bit j = qubit j): optimal, feasible."""
    m = qubo.num_vars
    X = enumerate_bitstrings(m).astype(float)
    energies = np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset
    opt_mask = np.isclose(energies, energies.min(), atol=1e-6)
    feas_mask = np.array([problem.is_feasible(x) for x in enumerate_bitstrings(m)])
    return opt_mask, feas_mask


def exact_distribution(ansatz, params):
    """Noiseless statevector probabilities of the tuned circuit (indexed by basis int)."""
    bound = ansatz.assign_parameters(list(params))
    return Statevector(bound).probabilities()


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

def optimize_params(targets, *, seed=QAOA_SEED, n_starts=N_STARTS, shots=SHOTS,
                    maxiter=MAXITER):
    """Re-optimize QAOA angles on the simulator; return one record per target.

    Reference metrics (ideal_opt_mass, ideal_feasibility) are the EXACT statevector
    values of the tuned circuit — the same 'exact' distribution stage (c) uses.
    """
    records = []
    for tgt in targets:
        T, s, reps = tgt["T"], tgt["seed"], tgt["reps"]
        problem, qubo, ansatz = build_target(T, s, reps)
        result = QAOASolver(reps=reps, n_starts=n_starts, shots=shots, seed=seed,
                            maxiter=maxiter).solve(problem, qubo)
        params = [float(x) for x in result.optimal_params]

        probs = exact_distribution(ansatz, params)
        opt_mask, feas_mask = basis_masks(problem, qubo)
        metrics = scalar_metrics(probs, opt_mask, feas_mask)
        records.append({
            "T": T, "seed": s, "reps": reps, "m": qubo.num_vars,
            "params": params,
            "dp_cost": float(dp_solve(problem).true_energy),
            "ideal_opt_mass": metrics["optimal_mass"],
            "ideal_feasibility": metrics["feasibility"],
            "stretch": bool(tgt.get("stretch", False)),
        })
    return records


def run_optimize(include_stretch=False):
    targets = list(PRIMARY_TARGETS)
    if include_stretch:
        targets += [dict(t, stretch=True) for t in STRETCH_TARGETS]
    records = optimize_params(targets)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PARAMS_PATH.write_text(json.dumps(records, indent=2))
    for r in records:
        print(f"T={r['T']} reps={r['reps']} m={r['m']} "
              f"ideal_opt_mass={r['ideal_opt_mass']:.4f} "
              f"ideal_feasibility={r['ideal_feasibility']:.4f}", flush=True)
    print(f"wrote {len(records)} records -> {PARAMS_PATH}", flush=True)


# --- stage (b): submit (sampling only; QPU-gated) ----------------------------

def _coarse_qpu_seconds(n_circuits, shots, depths):
    """Deliberately coarse order-of-magnitude estimate — NOT a quote.

    Actual QPU seconds are recorded post-run from job metadata.
    """
    per_circuit = 2.0 + shots * max(depths) * 2e-6
    return n_circuits * per_circuit


def run_submit(*, backend_name=None, include_stretch=False, yes_spend_qpu=False,
               shots=SHOTS):
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    records = json.loads(PARAMS_PATH.read_text())
    if not include_stretch:
        records = [r for r in records if not r.get("stretch")]
    if not records:
        raise SystemExit("no targets to submit (run `optimize` first)")

    # Bare service: saved default account in ~/.qiskit. No legacy channel.
    service = QiskitRuntimeService()
    max_m = max(r["m"] for r in records)
    backend = (service.backend(backend_name) if backend_name
               else service.least_busy(operational=True, simulator=False,
                                        min_num_qubits=max_m))
    pass_manager = generate_preset_pass_manager(optimization_level=1, backend=backend)

    circuits, labels = [], []
    for r in records:
        _, _, ansatz = build_target(r["T"], r["seed"], r["reps"])
        qc = ansatz.assign_parameters(r["params"])
        qc.measure_all()
        circuits.append(pass_manager.run(qc))
        labels.append(f"T{r['T']}_reps{r['reps']}")

    depths = [c.depth() for c in circuits]
    print("=== pre-submission summary ===")
    print(f"backend         : {backend.name}")
    print(f"jobs            : 1")
    print(f"circuits        : {len(circuits)}  ({', '.join(labels)})")
    print(f"shots/circuit   : {shots}")
    print(f"transpiled depth: {depths}")
    print(f"est. QPU seconds: ~{_coarse_qpu_seconds(len(circuits), shots, depths):.1f}  (COARSE)")

    if not yes_spend_qpu:
        print("DRY RUN — no QPU spent. Pass --yes-spend-qpu to submit.", flush=True)
        return

    sampler = SamplerV2(mode=backend)
    job = sampler.run([(c,) for c in circuits], shots=shots)
    print(f"submitted job {job.job_id()} to {backend.name}; waiting...", flush=True)
    result = job.result()

    try:
        actual_qpu_seconds = float(job.usage())
    except Exception:
        actual_qpu_seconds = None

    out = {
        "backend": backend.name,
        "job_id": job.job_id(),
        "shots": shots,
        "actual_qpu_seconds": actual_qpu_seconds,
        "results": [
            {**{k: records[i][k] for k in ("T", "seed", "reps", "m", "stretch")},
             "counts": result[i].data.meas.get_counts()}
            for i in range(len(records))
        ],
    }
    COUNTS_PATH.write_text(json.dumps(out, indent=2))
    print(f"actual QPU seconds: {actual_qpu_seconds}; wrote -> {COUNTS_PATH}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="stage", required=True)

    p_opt = sub.add_parser("optimize", help="stage (a): simulator re-optimization")
    p_opt.add_argument("--include-stretch", action="store_true")

    p_sub = sub.add_parser("submit", help="stage (b): sample on hardware (QPU-gated)")
    p_sub.add_argument("--backend", default=None)
    p_sub.add_argument("--include-stretch", action="store_true")
    p_sub.add_argument("--yes-spend-qpu", action="store_true")

    args = parser.parse_args()
    if args.stage == "optimize":
        run_optimize(include_stretch=args.include_stretch)
    elif args.stage == "submit":
        run_submit(backend_name=args.backend, include_stretch=args.include_stretch,
                   yes_spend_qpu=args.yes_spend_qpu)


if __name__ == "__main__":
    main()
