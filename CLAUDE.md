# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Quantum computing approach to solar panel placement optimization. The goal is to
formulate solar-panel siting/layout as an optimization problem and solve it with
quantum algorithms (via Qiskit), likely as a QUBO/Ising model attacked with QAOA
or similar variational methods on the Aer simulator.

## Architecture

The package lives in `src/quantum_solar/` (src layout — importable after
`pip install -e . --no-deps`). The pipeline is:

```
SolarProblem --build_qubo--> QUBO --+--> brute_force_solve --> Solution
                                    |
                                    +--qubo_to_ising--> QAOASolver.solve --> QAOAResult
```

Core design principle: the **true physical objective is kept separate from the
QUBO surrogate**.

- `problem.py` — `SolarProblem` owns the real physics: `energy(x)` (true yield =
  standalone yield minus pairwise shading loss) and `is_feasible(x)` (hard
  constraints: exactly `n_panels`, no pair closer than `min_spacing`).
  `random_instance(...)` builds reproducible instances.
- `qubo.py` — `build_qubo` folds the objective and the hard constraints (as
  weighted `PenaltyWeights`) into an upper-triangular `QUBO` (`xᵀQx + offset`).
- `ising.py` — `qubo_to_ising` maps the QUBO to a `SparsePauliOp` cost
  Hamiltonian via `x_i = (1 − z_i)/2`, returning `(H, constant)`. Invariant:
  `⟨x|H|x⟩ + constant == qubo.energy(x)` for every basis state.
- `qaoa.py` — `QAOASolver` runs QAOA on the Aer simulator. Hand-rolled from
  `QAOAAnsatz` + Aer `EstimatorV2`/`SamplerV2` + `scipy.optimize.minimize`
  (multi-start COBYLA), deliberately **not** `qiskit_algorithms`.
- `brute_force.py` — exact `2^M` enumeration; ground truth for QAOA. Refuses
  instances above `MAX_ENUMERATION_SITES` (20).
- Both solvers return the shared `Solution` type (`x`, `qubo_energy`,
  `true_energy`, `feasible`) so results are directly comparable.

Gotchas:
- QAOA transpiles for an `AerSimulator` with **no coupling map**, so the layout
  is trivial and sampled bitstrings are plain little-endian. `_counts_key_to_x`
  handles the endianness (Qiskit's leftmost char is the highest qubit).
- `QAOAAnsatz` emits an `NLocal`/`BlueprintCircuit` `DeprecationWarning`
  (Qiskit 2.1, removal in 3.0). Functional for now; revisit before a Qiskit 3
  upgrade.

## Environment & Commands

A virtualenv already exists at `.venv` (Python 3.12).

```bash
source .venv/bin/activate         # activate the environment
pip install -r requirements.txt   # sync deps (already installed in .venv)
pip install -e . --no-deps        # make `import quantum_solar` work (src layout)

python -m pytest                  # full suite (~10s; includes slow QAOA runs)
python -m pytest -m "not slow"    # fast unit tests only, skip Aer end-to-end
python -m pytest tests/test_ising.py::test_roundtrip_tiny   # a single test
python -m pytest -m slow          # only the end-to-end QAOA vs brute-force tests

jupyter lab                       # interactive/quantum work in notebooks/
```

No linter is configured. The slow marker gates the Aer-backed QAOA tests
(defined in `pyproject.toml`).

## Stack

- **Qiskit 2.x** (`qiskit`) — quantum circuit construction and algorithms.
- **qiskit-aer** — local high-performance simulator; the default backend for
  running/optimizing circuits without real quantum hardware.
- **numpy / scipy** — numerical work and classical optimizers (e.g. for the
  variational parameter loop in QAOA/VQE-style algorithms).
- **matplotlib** — visualization of layouts, results, and circuits.
- **Jupyter / JupyterLab** — primary interactive development surface.

## Testing

- Use **pytest**. Write unit tests for the physics model and the optimization
  code.
- Validate QAOA output against **classical brute-force enumeration** on small
  problem instances. Small placement problems can be enumerated exactly, so the
  brute-force optimum is ground truth — assert the quantum result matches (or is
  within tolerance of) it before trusting the algorithm on larger instances.

## Code quality

- Prioritize correctness and efficiency.
- Prefer vectorized NumPy over Python loops for numerical work.

## Conventions

- `requirements.txt` is fully pinned (exact versions). Keep it that way and
  update it whenever adding a dependency.
- Commit attribution is intentionally disabled in `.claude/settings.json`
  (empty `commit`/`pr` trailers) — do not add co-author/attribution trailers.
