"""How much optimality does each slack-free SoC encoding give up, and what does it
cost on hardware?

Two independent axes, reported side by side because they rank candidates
differently:

*Solution quality* — ``dp_solve`` is exact and independent of the QUBO, so for
every instance we compare the surrogate's exact optimum (``qubo_min_exact``)
against the true optimum. An encoding can fail two ways, and they are not
interchangeable: it can return an **infeasible** schedule (the bounds it dropped
were load-bearing), or a feasible but **suboptimal** one. Regret is normalized by
the battery's whole value — ``(cost_no_battery − cost_optimal)`` — so 100% means
the encoding captured none of it.

*Hardware cost* — qubit count is **not** the binding constraint. July's run
established that device-noise TVD tracks transpiled two-qubit gate count
monotonically (37/77/124/290 gates -> 0.119/0.203/0.383/0.459 TVD), and the two
6-qubit circuits in that set differ by 0.084 TVD from depth alone at *identical*
qubit count. So the ranking that matters is on gates, and this script transpiles
each candidate against a real Heron coupling map to get it.

Both ``optimization_level`` 1 and 3 are reported: level 1 is what
``scripts/experiment_hardware.py`` actually submits with (and is what produced
July's counts), level 3 is what it could submit with. Where the two differ
materially, that difference is free.

Run::

    python scripts/encoding_study.py [--seeds N] [--slots 4,6,8,12,24]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quantum_solar import (  # noqa: E402
    Encoding,
    build_qubo,
    default_weights,
    dp_solve,
    max_sound_spacing,
    num_vars,
    qubo_to_ising,
    synthetic_instance,
)
from quantum_solar.qubo_search import qubo_min_exact  # noqa: E402

# Instance family. Matches scripts/experiment_hardware.py so the hardware numbers
# here are directly comparable to July's.
CAPACITY, CHARGE_ENERGY, INITIAL_SOC = 3.0, 1.0, 1.0

# Checkpoint spacing is PINNED, not derived from the instance. max_sound_spacing
# reports the ceiling; inheriting it silently would let the encoding's rigidity
# drift with initial_soc between instances and make the columns incomparable.
CHECKPOINT_SPACING = 3
DRIFT_WINDOW = 4

# Transpiling a 90-qubit fully-connected QUBO is slow and pointless — nothing that
# size is submittable. Above this, the hardware columns read "n/a".
MAX_TRANSPILE_QUBITS = 28


@dataclass(frozen=True)
class Quality:
    """Solution-quality outcome for one encoding over a set of instances."""

    n: int
    n_infeasible: int
    n_exact: int
    regret: float | None  # None => undefined: every instance came back infeasible

    @property
    def infeasible_pct(self) -> float:
        return 100.0 * self.n_infeasible / self.n

    @property
    def exact_pct(self) -> float:
        return 100.0 * self.n_exact / self.n

    def regret_str(self) -> str:
        if self.regret is None:
            return "undefined (all infeasible)"
        # Regret is a gap against the exact optimum, so it cannot be negative;
        # clamp the float dust that would otherwise print as a bogus "-0.00".
        return f"{max(self.regret, 0.0):.2f}"


@dataclass(frozen=True)
class Hardware:
    """Transpiled cost of one encoding's QAOA circuit on a real backend."""

    qubits: int
    couplings: int
    gates_o1: int | None  # None => not transpiled (too large to be submittable)
    depth_o1: int | None
    gates_o3: int | None
    depth_o3: int | None


def instance(t: int, seed: int):
    return synthetic_instance(
        t,
        seed=seed,
        capacity=CAPACITY,
        charge_energy=CHARGE_ENERGY,
        discharge_energy=CHARGE_ENERGY,
        initial_soc=INITIAL_SOC,
    )


def candidates(t: int, problem) -> list[tuple[str, object]]:
    """The encodings under test, with the pinned spacing checked for soundness."""
    ceiling = max_sound_spacing(problem)
    if CHECKPOINT_SPACING > ceiling:
        raise ValueError(
            f"pinned CHECKPOINT_SPACING={CHECKPOINT_SPACING} exceeds the sound "
            f"ceiling {ceiling} for this instance family (capacity={CAPACITY}, "
            f"initial_soc={INITIAL_SOC}); lower it rather than deriving it."
        )
    return [
        ("exact", Encoding.EXACT),
        (f"cp{CHECKPOINT_SPACING}", Encoding.checkpoint(CHECKPOINT_SPACING)),
        (f"cp{CHECKPOINT_SPACING}band", Encoding.checkpoint(CHECKPOINT_SPACING, banded=True)),
        (f"wd{min(DRIFT_WINDOW, t)}", Encoding.window_drift(min(DRIFT_WINDOW, t))),
        ("center", Encoding.center_anchor()),
        ("none", Encoding.NONE),
    ]


def measure_quality(t: int, encoding, seeds) -> Quality:
    n_infeasible = n_exact = 0
    regrets: list[float] = []
    for seed in seeds:
        problem = instance(t, seed)
        got = qubo_min_exact(problem, default_weights(problem), encoding)
        truth = dp_solve(problem)
        if not got.feasible:
            n_infeasible += 1
            continue
        no_battery = float(problem.price @ (problem.load - problem.generation))
        value = max(no_battery - truth.true_energy, 1e-12)
        gap = got.true_energy - truth.true_energy
        regrets.append(gap / value)
        if gap < 1e-9:
            n_exact += 1
    return Quality(
        n=len(seeds),
        n_infeasible=n_infeasible,
        n_exact=n_exact,
        regret=(100.0 * float(np.mean(regrets)) if regrets else None),
    )


def measure_hardware(problem, encoding, backend, reps: int) -> Hardware:
    """Transpile the QAOA circuit for ``backend`` and count what the device sees."""
    from qiskit.circuit.library import QAOAAnsatz
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

    qubo = build_qubo(problem, default_weights(problem), encoding)
    off_diagonal = np.triu(np.abs(qubo.Q), k=1)
    couplings = int(np.count_nonzero(off_diagonal > 1e-12))
    if qubo.num_vars > MAX_TRANSPILE_QUBITS:
        return Hardware(qubo.num_vars, couplings, None, None, None, None)

    hamiltonian, _ = qubo_to_ising(qubo)
    ansatz = QAOAAnsatz(cost_operator=hamiltonian, reps=reps)
    out: dict[int, tuple[int, int]] = {}
    for level in (1, 3):
        pm = generate_preset_pass_manager(optimization_level=level, backend=backend)
        circuit = pm.run(ansatz)
        ops = circuit.count_ops()
        two_qubit = sum(n for gate, n in ops.items() if gate in ("cz", "cx", "ecr"))
        out[level] = (two_qubit, circuit.depth())
    return Hardware(qubo.num_vars, couplings, *out[1], *out[3])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=40)
    parser.add_argument("--slots", default="4,6,8,12,24")
    parser.add_argument("--reps", type=int, default=1)
    args = parser.parse_args()

    from qiskit_ibm_runtime.fake_provider import FakeFez

    backend = FakeFez()
    seeds = range(args.seeds)
    slots = [int(s) for s in args.slots.split(",")]

    print(f"backend={backend.name}  reps={args.reps}  seeds={args.seeds}  "
          f"checkpoint spacing pinned at {CHECKPOINT_SPACING}\n")
    header = (f"{'T':>3} {'encoding':<9} {'qubits':>6} {'2Q(o1)':>7} {'d(o1)':>6} "
              f"{'2Q(o3)':>7} {'d(o3)':>6} {'infeas%':>8} {'exact%':>7} {'regret':>26}")
    print(header)
    print("-" * len(header))
    for t in slots:
        problem = instance(t, seeds[0])
        for name, encoding in candidates(t, problem):
            hw = measure_hardware(problem, encoding, backend, args.reps)
            q = measure_quality(t, encoding, seeds)
            fmt = lambda v: "n/a" if v is None else str(v)  # noqa: E731
            print(f"{t:>3} {name:<9} {hw.qubits:>6} {fmt(hw.gates_o1):>7} "
                  f"{fmt(hw.depth_o1):>6} {fmt(hw.gates_o3):>7} {fmt(hw.depth_o3):>6} "
                  f"{q.infeasible_pct:>8.1f} {q.exact_pct:>7.1f} {q.regret_str():>26}")
        print()


if __name__ == "__main__":
    main()
